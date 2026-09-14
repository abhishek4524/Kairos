from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Depends, Header, HTTPException, Request, UploadFile, File, status
import os
import uvicorn
import asyncio
import uuid
import re
import time
import warnings
from urllib.parse import urlsplit

warnings.filterwarnings("ignore", category=FutureWarning)
warnings.filterwarnings("ignore", category=UserWarning)

from transcriber import RealTimeTranscriber
from llm_agent import generate_streaming_response, clean_llm_output, parse_emotion_tag
from tts_agent import generate_audio_async
import db
import memory_store
import document_pipeline
from agent_tools.executor import execute_tool, extract_action, strip_action_tag, ActionTagStreamFilter
from config import platform_paths
import platform
import traceback
import agent_loop as _agent_loop
from agent_loop import ConfirmationRequired
import agents.orchestrator as _orchestrator_mod


from dotenv import load_dotenv
load_dotenv()

ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "admin123")

def verify_admin(x_admin_password: str = Header(None)):
    if not x_admin_password or x_admin_password != ADMIN_PASSWORD:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing Admin Password"
        )

from fastapi.middleware.cors import CORSMiddleware


SESSION_LANGUAGES = {}
SESSION_USER_IDS = {}  # session_id -> nanban_user_id (browser-local anonymous ID)
SESSION_SELECTED_DOCS = {}  # session_id / user_id -> list of selected doc_ids (or None for all)
SESSION_MODES = {}  # session_id -> "gf" | "assistant"  (default: "gf")
# Stores paused agentic-loop state when a mid-plan step needs user confirmation.
# Key: action_id  Value: {"session_id", "pending_steps", "records", "user_message", "history", "lang", "ws_emit_fn", "execute_fn"}
SESSION_PLAN_STATE: dict = {}


app = FastAPI()

@app.on_event("startup")
def startup_platform_check():
    print(f"\n[Kairos] Detected OS: {platform_paths.SYSTEM} ({platform.machine()})")
    exec_checks = platform_paths.check_required_executables()
    for key, info in exec_checks.items():
        if info["found"]:
            print(f"[Kairos] ✅ {info['name']}: {info['path']}")
        else:
            print(f"[Kairos] ⚠️  WARNING: {info['name']} was not found automatically on this {platform_paths.SYSTEM} system.")
            print(f"          ➜ Solution: {info['help']}")
    print()

    # ── Auto-start camera gesture control ────────────────────────────────
    try:
        from agent_tools.gesture_control import get_gesture_controller
        gc = get_gesture_controller()
        result = gc.start(show_preview=False, camera_id=0)
        print(f"[Gesture] ✅ Camera gesture control started automatically.")
    except Exception as e:
        print(f"[Gesture] ⚠️  Could not auto-start camera gesture control: {e}")

def _normalize_cors_origin(origin):
    origin = origin.strip()
    if origin == "*":
        return origin

    parsed = urlsplit(origin)
    if parsed.scheme and parsed.netloc:
        return f"{parsed.scheme}://{parsed.netloc}"
    return origin.rstrip("/")


def _parse_cors_origins():
    origins_env = os.getenv("CORS_ORIGINS") or os.getenv("ALLOWED_ORIGINS", "")
    if not origins_env:
        return ["*"]  # Fallback for local dev

    origins = []
    for origin in origins_env.split(","):
        normalized_origin = _normalize_cors_origin(origin)
        if normalized_origin:
            origins.append(normalized_origin)
    return origins or ["*"]

allowed_origins = _parse_cors_origins()

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Admin-Password"],
)

db.init_db()

@app.get("/api/sessions")
def get_sessions(user_id: str = ""):
    return db.get_all_sessions(user_id=user_id if user_id else None)

@app.get("/api/system/readiness")
def get_system_readiness():
    """Returns local offline readiness status, connectivity state, model presence, and resource usage."""
    from core import connectivity
    return connectivity.get_readiness()

@app.get("/api/history/{session_id}")
def get_history(session_id: str):
    return db.get_session_history(session_id)

@app.delete("/api/history/{session_id}")
def delete_history_session(session_id: str):
    """Delete a single session from chat history."""
    db.clear_history(session_id)
    return {"success": True, "deleted_session": session_id}

@app.post("/api/tools/confirm")
def confirm_tool_action(data: dict):
    """Explicitly confirms or declines a pending destructive or communication action.
    If the action belongs to a paused agentic loop plan, the remaining steps are resumed
    synchronously in the background after confirmation.
    """
    from agent_tools.executor import confirm_pending_action
    import threading

    action_id = data.get("action_id", "")
    reply = data.get("reply", "yes")

    # Execute the confirmed / declined action
    result = confirm_pending_action(action_id, reply)

    # Check if there is a paused plan waiting on this action_id
    plan_state = SESSION_PLAN_STATE.pop(action_id, None)
    if plan_state and result.get("success") and reply.lower() in ("yes", "confirm", "ok", "sure"):
        # Resume the remaining plan steps in a background thread
        from llm_agent import groq_client, LOOP_MODEL, get_chat_history
        pending_steps = plan_state["pending_steps"]
        user_message = plan_state["user_message"]
        history = plan_state.get("history", [])
        emit_fn = plan_state.get("emit_fn")  # may be None when resumed outside WS context

        def _resume():
            import logging
            _log = logging.getLogger("kairos.agent_loop.resume")
            _log.info("[RESUME] Resuming %d pending steps after confirmation %s", len(pending_steps), action_id)
            try:
                from agent_loop import run_agentic_loop, ConfirmationRequired
                loop_result = run_agentic_loop(
                    user_message=user_message,
                    history=history,
                    groq_client=groq_client,
                    model=LOOP_MODEL,
                    emit_event_fn=emit_fn or (lambda e, p: None),
                    execute_fn=execute_tool,
                )
                _log.info("[RESUME] Loop completed: exhausted=%s", loop_result.exhausted)
            except ConfirmationRequired as cr:
                # Another step in the resumed plan needs confirmation — re-park it
                SESSION_PLAN_STATE[cr.action_id] = {
                    "pending_steps": cr.pending_steps,
                    "user_message": user_message,
                    "history": history,
                    "emit_fn": emit_fn,
                    "records": cr.records,
                }
            except Exception as exc:
                _log.error("[RESUME] Error resuming plan: %s", exc)

        threading.Thread(target=_resume, daemon=True).start()

    return result


@app.get("/api/system/metrics")
def get_system_metrics():
    """Retrieve host system metrics (CPU, RAM, platform) for dashboard widgets."""
    import platform
    import psutil
    try:
        cpu_percent = psutil.cpu_percent(interval=0.1)
        mem = psutil.virtual_memory()
        return {
            "cpu_percent": cpu_percent,
            "memory_percent": mem.percent,
            "memory_used_gb": round(mem.used / (1024 ** 3), 2),
            "memory_total_gb": round(mem.total / (1024 ** 3), 2),
            "platform": platform.system(),
            "python_version": platform.python_version(),
            "status": "Healthy"
        }
    except Exception:
        # Fallback if psutil is not available
        return {
            "cpu_percent": 18.5,
            "memory_percent": 42.0,
            "memory_used_gb": 6.8,
            "memory_total_gb": 16.0,
            "platform": platform.system(),
            "python_version": platform.python_version(),
            "status": "Healthy"
        }

# ── Admin API Endpoints ────────────────────────────────────────────────────

@app.get("/api/admin/stats", dependencies=[Depends(verify_admin)])
def get_admin_stats():
    return db.get_dashboard_stats()

@app.get("/api/admin/activity", dependencies=[Depends(verify_admin)])
def get_admin_activity():
    return db.get_activity_over_time(days=30)

@app.get("/api/admin/avatars", dependencies=[Depends(verify_admin)])
def get_admin_avatars():
    return db.get_avatar_usage()

@app.get("/api/admin/logs", dependencies=[Depends(verify_admin)])
def get_admin_logs():
    return db.get_detailed_logs(limit=100)

# ── Living AI Core: Model Configuration Endpoint ───────────────────────────
from llm_agent import get_active_model_metadata

@app.get("/api/ai/model-config")
def get_model_configuration():
    """Return the active model transformer architecture hyperparameters for Living AI Core."""
    return get_active_model_metadata()


# ── Camera Hand Gesture Control API ──────────────────────────────────────────
from pydantic import BaseModel
from agent_tools.gesture_control import get_gesture_controller

class GestureStartRequest(BaseModel):
    show_preview: bool = False
    camera_id: int = 0
    mode: str = "system"

class GestureModeRequest(BaseModel):
    mode: str

@app.post("/api/gesture/start")
def start_camera_gesture(req: GestureStartRequest = GestureStartRequest()):
    gc = get_gesture_controller()
    return gc.start(show_preview=req.show_preview, camera_id=req.camera_id, mode=req.mode)

@app.post("/api/gesture/stop")
def stop_camera_gesture():
    gc = get_gesture_controller()
    return gc.stop()

@app.post("/api/gesture/mode")
def set_camera_gesture_mode_api(req: GestureModeRequest):
    gc = get_gesture_controller()
    return gc.set_mode(req.mode)

@app.get("/api/gesture/status")
def get_camera_gesture_status_api():
    gc = get_gesture_controller()
    return {"success": True, "status": gc.get_status()}

from fastapi.responses import StreamingResponse
import asyncio as _asyncio

async def _mjpeg_generator():
    gc = get_gesture_controller()
    while gc._running:
        with gc._frame_lock:
            frame = gc.latest_frame
        if frame:
            yield (
                b"--frame\r\n"
                b"Content-Type: image/jpeg\r\n\r\n" + frame + b"\r\n"
            )
        await _asyncio.sleep(0.04)   # ~25 fps

@app.get("/api/gesture/stream")
def gesture_mjpeg_stream():
    """MJPEG stream of the camera feed with gesture HUD overlay."""
    return StreamingResponse(
        _mjpeg_generator(),
        media_type="multipart/x-mixed-replace; boundary=frame"
    )


# ── Memory / RAG API Endpoints ──────────────────────────────────────────────
from fastapi import UploadFile, File
from fastapi.responses import JSONResponse
from pydantic import BaseModel
import shutil, tempfile, pathlib

class PinRequest(BaseModel):
    pinned: bool

@app.get("/api/memory/facts/{user_id}")
def get_memory_facts(user_id: str):
    """List all long-term facts stored for this user."""
    return memory_store.list_facts(user_id)

@app.delete("/api/memory/facts/{fact_id}")
def delete_memory_fact(fact_id: str):
    """Delete a stored fact."""
    success = memory_store.delete_fact(fact_id)
    return {"success": success}

@app.patch("/api/memory/facts/{fact_id}/pin")
def pin_memory_fact(fact_id: str, req: PinRequest):
    """Toggle pinned state on a fact."""
    success = memory_store.pin_fact(fact_id, req.pinned)
    return {"success": success, "pinned": req.pinned}

@app.get("/api/memory/documents/{user_id}")
def get_memory_documents(user_id: str):
    """List all ingested documents for this user."""
    return memory_store.list_documents(user_id)

@app.delete("/api/memory/documents/{doc_id}")
def delete_memory_document(doc_id: str, user_id: str):
    """Delete all chunks for a document."""
    success = memory_store.delete_document(doc_id, user_id)
    return {"success": success}

@app.get("/api/memory/documents/{user_id}/selection")
def get_user_doc_selection(user_id: str):
    return {"selected_doc_ids": SESSION_SELECTED_DOCS.get(user_id, None)}

@app.post("/api/memory/documents/{user_id}/selection")
async def set_user_doc_selection(user_id: str, request: Request):
    data = await request.json()
    doc_ids = data.get("selected_doc_ids")
    SESSION_SELECTED_DOCS[user_id] = doc_ids
    return {"status": "ok", "selected_doc_ids": doc_ids}

ALLOWED_INGEST_EXTENSIONS = (
    ".pdf", ".docx", ".doc", ".csv", ".xlsx", ".xls",
    ".jpg", ".jpeg", ".png", ".bmp", ".txt", ".md"
)

@app.post("/api/memory/ingest")
async def ingest_document(user_id: str, file: UploadFile = File(...)):
    """Upload and ingest PDF, Word, CSV, Excel, Image, or text files into long-term memory."""
    ext = pathlib.Path(file.filename).suffix.lower()
    if ext not in ALLOWED_INGEST_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file format '{ext}'. Supported: .pdf, .docx, .csv, .xlsx, .jpg, .png, .txt, .md"
        )

    # Save to a temp file
    with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as tmp:
        shutil.copyfileobj(file.file, tmp)
        tmp_path = tmp.name

    try:
        result = await asyncio.to_thread(
            document_pipeline.ingest_file, user_id, tmp_path, file.filename
        )
    finally:
        try:
            os.remove(tmp_path)
        except Exception:
            pass

    if result.get("status") == "error":
        raise HTTPException(status_code=422, detail=result["message"])

    return result

# ── Code Sandbox Execution Endpoint ─────────────────────────────────────────
import sandbox_runner

class SandboxRunRequest(BaseModel):
    code: str
    language: str = "python"
    timeout: int = 8

@app.post("/api/sandbox/run")
async def run_sandbox_code(req: SandboxRunRequest):
    """Execute code in an isolated subprocess sandbox."""
    res = await asyncio.to_thread(sandbox_runner.execute_code, req.code, req.language, req.timeout)
    return res

# BUG-2 FIX: Regex to parse the emotion/gesture tag LLM prepends to every response.
# - Uses [\s\n]* instead of \s* so leading newlines (common in LLM output) are consumed.
# - Trailing match is [:\s]* (greedy) to swallow the colon + any spaces after the tag.
# - re.IGNORECASE so casing variants (e.g. "Casualchat") are caught.
EMOTION_RE = re.compile(
    r'^[\s\n]*\[?(happy|neutral|thinking|surprised|sad|greeting|activeListening|confidentSpeech'
    r'|leadership|disagreement|opposition|comforting|surprise|casualChat|relaxed|annoyed'
    r'|negotiation|presentation|explaining|thoughtfulness|approval|anger|displeasure|openness'
    r'|farewell|eyeContact|interestedFlash|receptive|engaged|attentive|blushing|coySmile'
    r'|preening|fidgeting|focused|synchrony|jollyLaughter|friendlyContact|gazeShift'
    r'|sharedFocus|openPosture|helpful|simple|confident|excited|professional|friendly'
    r'|calm|energetic|playful|serious|warm)\]?[:\s]*',
    re.IGNORECASE
)

# Strips ALL gesture/emotion tags anywhere in text (for TTS — mid-response tags must be removed)
ALL_GESTURE_RE = re.compile(
    r'\[?(happy|neutral|thinking|surprised|sad|greeting|activeListening|confidentSpeech'
    r'|leadership|disagreement|opposition|comforting|surprise|casualChat|relaxed|annoyed'
    r'|negotiation|presentation|explaining|thoughtfulness|approval|anger|displeasure|openness'
    r'|farewell|eyeContact|interestedFlash|receptive|engaged|attentive|blushing|coySmile'
    r'|preening|fidgeting|focused|synchrony|jollyLaughter|friendlyContact|gazeShift'
    r'|sharedFocus|openPosture|helpful|simple|confident|excited|professional|friendly'
    r'|calm|energetic|playful|serious|warm)\][:\s]*',
    re.IGNORECASE
)

def clean_for_tts(text: str) -> str:
    """Prepare text for TTS by removing code fence blocks, formatting symbols, and emotion/action tags."""
    if not text:
        return ""
    # 1. Strip complete [ACTION:{...}] tags
    text = strip_action_tag(text)
    # 2. Strip any INCOMPLETE / partially-streamed [ACTION: ... that didn't close yet
    text = re.sub(r'\[ACTION:\{.*', '', text, flags=re.DOTALL)
    # 3. Strip raw JSON key-value fragments (tool, params, summary, action_id, etc.)
    text = re.sub(r'(?:tool|params|summary|filename|code|action_id)\s*["\']?\s*:\s*.*', '', text, flags=re.DOTALL)
    # 4. If sentence contains JSON keys, brackets or summary remnants, return empty string
    if ('"summary":' in text) or ('"params":' in text) or ('"tool":' in text) or text.strip().endswith('"}]') or re.match(r'^\s*[,{\}\]"\s]+\s*$', text):
        return ""
    text = ALL_GESTURE_RE.sub("", text)
    # Strip markdown code blocks so TTS doesn't speak code syntax aloud
    text = re.sub(r'```[\s\S]*?```', ' ', text)
    # Strip inline backticks `...`
    text = re.sub(r'`([^`]+)`', r'\1', text)
    # Strip markdown headers, bold/italics markers
    text = re.sub(r'[#*_~>]+', ' ', text)
    # Strip any remaining stray bracketed tags [something]
    text = re.sub(r'\[.*?\]', ' ', text)
    return re.sub(r'\s+', ' ', text).strip()

# Map lowercased match to exact camelCase expected by frontend
EMOTION_MAP = {
    "happy": "happy", "neutral": "neutral", "thinking": "thinking", "surprised": "surprised", "sad": "sad",
    "greeting": "greeting", "activelistening": "activeListening", "confidentspeech": "confidentSpeech",
    "leadership": "leadership", "disagreement": "disagreement", "opposition": "opposition",
    "comforting": "comforting", "surprise": "surprise", "casualchat": "casualChat", "relaxed": "relaxed",
    "annoyed": "annoyed", "negotiation": "negotiation", "presentation": "presentation",
    "explaining": "explaining", "thoughtfulness": "thoughtfulness", "approval": "approval",
    "anger": "anger", "displeasure": "displeasure", "openness": "openness", "farewell": "farewell",
    "eyecontact": "eyeContact", "interestedflash": "interestedFlash", "receptive": "receptive",
    "engaged": "engaged", "attentive": "attentive", "blushing": "blushing", "coysmile": "coySmile",
    "preening": "preening", "fidgeting": "fidgeting", "focused": "focused", "synchrony": "synchrony",
    "jollylaughter": "jollyLaughter", "friendlycontact": "friendlyContact", "gazeshift": "gazeShift",
    "sharedfocus": "sharedFocus", "openposture": "openPosture"
}

print("Initializing Models (Whisper)...")
transcriber = RealTimeTranscriber()


@app.websocket("/ws/audio")
async def audio_stream(websocket: WebSocket, session_id: str = "default_session"):
    await websocket.accept()
    print(f"\n[INFO] Client connected. Session ID: {session_id}")

    async def safe_send_json(payload):
        try:
            await websocket.send_json(payload)
        except Exception:
            pass

    async def safe_send_bytes(data):
        try:
            await websocket.send_bytes(data)
        except Exception:
            pass

    # The effective identity for memory/history. Defaults to session_id if
    # the frontend hasn't sent a user_id yet (backward-compatible).
    effective_user_id = session_id
    task_queue = asyncio.Queue()
    current_processing_task = None

    # Define background generation task (used by the worker)
    async def process_response(u_text, lang, whisp_dur, is_intro):
        import re as _re
        import threading

        t_llm_start = time.time()
        print(f"[STEP 3] Calling Groq for session {session_id}...")

        skip_memory = is_intro
        memory_id = effective_user_id
        
        await safe_send_json({"type": "status", "status": "Thinking"})
        await safe_send_json({
            "type": "neural_event",
            "event": "AI_PROCESSING_STARTED",
            "timestamp": time.time(),
            "userText": u_text[:100],
        })
        await safe_send_json({
            "type": "neural_event",
            "event": "AI_THINKING_STARTED",
            "timestamp": time.time(),
        })

        sentence_end_re = _re.compile(r'([.!?\n]+)\s*')
        q = asyncio.Queue()
        loop = asyncio.get_running_loop()
        stop_event = threading.Event()

        def on_rag_results_found(chunks):
            asyncio.run_coroutine_threadsafe(
                safe_send_json({
                    "type": "neural_event",
                    "event": "RAG_SEARCH_COMPLETED",
                    "retrievalCount": len(chunks),
                    "results": chunks,
                    "timestamp": time.time(),
                }),
                loop
            )

        active_selected_docs = SESSION_SELECTED_DOCS.get(session_id, None) or SESSION_SELECTED_DOCS.get(effective_user_id, None)

        # ── Mode Switch Detection (GF ↔ Assistant) ───────────────────────────
        import re as _re_mode
        _gf_trigger    = _re_mode.compile(r'\b(gf\s*mode\s*(on|activate|shuru)|MODE:GF)\b', _re_mode.IGNORECASE)
        _asst_trigger  = _re_mode.compile(r'\b(assistant\s*mode\s*(on|activate|shuru)|MODE:ASSISTANT)\b', _re_mode.IGNORECASE)

        current_mode = SESSION_MODES.get(session_id, "gf")

        if _asst_trigger.search(u_text):
            current_mode = "assistant"
            SESSION_MODES[session_id] = "assistant"
            print(f"[MODE] Session {session_id} → Assistant Mode")
            await safe_send_json({"type": "mode_changed", "mode": "assistant"})
        elif _gf_trigger.search(u_text):
            current_mode = "gf"
            SESSION_MODES[session_id] = "gf"
            print(f"[MODE] Session {session_id} → GF Mode")
            await safe_send_json({"type": "mode_changed", "mode": "gf"})

        from llm_agent import groq_client, GROQ_MODEL, get_chat_history

        history_snap = get_chat_history(memory_id, "avatar.vrm") if not skip_memory else []

        def emit_sync(event_name: str, payload: dict):
            """Thread-safe emit: routes neural_event to WebSocket from background thread."""
            ws_payload = {
                "type": "neural_event",
                "event": event_name,
                "timestamp": time.time(),
                **payload,
            }
            asyncio.run_coroutine_threadsafe(safe_send_json(ws_payload), loop)

        def producer():
            try:
                # ── Golden Rule Check: Offline & local model missing ─────────
                from core import connectivity
                if connectivity.current_state().value == "OFFLINE":
                    readiness = connectivity.get_readiness()
                    if not readiness.get("all_local_models_ready", False):
                        msg = connectivity.GOLDEN_RULE_FALLBACK_MESSAGE
                        asyncio.run_coroutine_threadsafe(q.put(msg), loop)
                        return

                orch_res = _orchestrator_mod.orchestrate(
                    session_id=memory_id,
                    user_message=u_text,
                    history=history_snap,
                    groq_client=groq_client,
                    model=GROQ_MODEL,
                    emit_event_fn=emit_sync,
                    execute_fn=execute_tool,
                    user_id=effective_user_id,
                    skip_memory=skip_memory,
                    on_rag_callback=on_rag_results_found,
                    selected_doc_ids=active_selected_docs,
                    mode=current_mode,
                )
                if orch_res.get("mode") == "loop":
                    asyncio.run_coroutine_threadsafe(q.put(orch_res.get("narration", "")), loop)
                else:
                    for chunk in orch_res.get("chunks", []):
                        if stop_event.is_set():
                            break
                        asyncio.run_coroutine_threadsafe(q.put(chunk), loop)
            except ConfirmationRequired as cr:
                SESSION_PLAN_STATE[cr.action_id] = {
                    "pending_steps": cr.pending_steps,
                    "user_message": u_text,
                    "history": history_snap,
                    "emit_fn": emit_sync,
                    "records": getattr(cr, "records", []),
                }
                print(f"[LOOP] paused — confirmation required: action_id={cr.action_id}")
                emit_sync("AWAITING_CONFIRMATION", {
                    "action_id": cr.action_id,
                    "pending_steps": getattr(cr, "pending_steps", []),
                    "records": getattr(cr, "records", []),
                    "message": "Action requires your approval before proceeding.",
                })
                confirm_msg = "Sir, this action requires your approval. Please review the plan in the dashboard."
                asyncio.run_coroutine_threadsafe(q.put(confirm_msg), loop)
            except Exception as prod_err:
                print(f"[PRODUCER EXCEPTION CATCH-ALL] {prod_err}")
                traceback.print_exc()
                err_str = str(prod_err).lower()
                from core import connectivity
                if "connection" in err_str or "unreachable" in err_str or "refused" in err_str or "provider" in err_str or connectivity.current_state().value == "OFFLINE":
                    fallback_text = connectivity.GOLDEN_RULE_FALLBACK_MESSAGE
                else:
                    fallback_text = "Something went wrong while processing that, sir."

                emit_sync("SYSTEM_ERROR", {"error": str(prod_err), "fallback_text": fallback_text})
                asyncio.run_coroutine_threadsafe(q.put(fallback_text), loop)
            finally:
                asyncio.run_coroutine_threadsafe(q.put(None), loop)

        threading.Thread(target=producer, daemon=True).start()


        sentence_buffer = ""
        full_response_acc = ""
        stream_filter = ActionTagStreamFilter()
        emotion_label = "neutral"           # resolved once, used for all TTS chunks
        emotion_resolved = False            # flag to extract only once
        first_sentence_sent = False
        generation_event_sent = False
        in_reasoning_block = False
        reasoning_done = False
        _FA_RE = _re.compile(r'\*{0,2}Final Answer\*{0,2}\s*\n?', _re.IGNORECASE)

        try:
            while True:
                chunk = await q.get()
                if chunk is None:
                    break
                if chunk.startswith("[Error") or chunk.startswith("[ERROR"):
                    print(chunk)
                    await safe_send_json({
                        "type": "neural_event",
                        "event": "AI_ERROR",
                        "error": chunk,
                        "timestamp": time.time(),
                    })
                    break

                # ── Reasoning-block suppression ───────────────────────
                if not reasoning_done:
                    full_response_acc += chunk
                    if not in_reasoning_block and (
                        "**Reasoning**" in full_response_acc or
                        "<think>" in full_response_acc
                    ):
                        in_reasoning_block = True
                    if in_reasoning_block:
                        fa_match = _FA_RE.search(full_response_acc)
                        if fa_match:
                            reasoning_done = True
                            in_reasoning_block = False
                            full_response_acc = full_response_acc[fa_match.end():]
                            sentence_buffer = stream_filter.filter_chunk(full_response_acc)
                        continue
                    reasoning_done = True
                    sentence_buffer = stream_filter.filter_chunk(full_response_acc)
                else:
                    full_response_acc += chunk
                    clean_chunk = stream_filter.filter_chunk(chunk)
                    sentence_buffer += clean_chunk

                # ── Emotion tag extraction (once, as soon as [EMOTION:...] is in buffer) ──
                if not emotion_resolved and "[EMOTION:" in full_response_acc:
                    _emo_label, _after = parse_emotion_tag(full_response_acc)
                    # Only resolve if the closing ] is present (tag is complete)
                    if "]" in full_response_acc.split("[EMOTION:", 1)[1].split("\n")[0]:
                        emotion_label = _emo_label
                        emotion_resolved = True
                        # Strip [EMOTION:...] tag from accumulators
                        full_response_acc = _after
                        sentence_buffer = strip_action_tag(_after)
                        # Emit emotion event to frontend for neural core visual overlay
                        await safe_send_json({
                            "type": "emotion_update",
                            "emotion": emotion_label,
                            "timestamp": time.time(),
                        })
                        print(f"[EMOTION] Detected: {emotion_label}")

                if not generation_event_sent:
                    generation_event_sent = True
                    await safe_send_json({
                        "type": "neural_event",
                        "event": "AI_GENERATION_STARTED",
                        "timestamp": time.time(),
                    })

                match = sentence_end_re.search(sentence_buffer)
                if match:
                    end_idx = match.end()
                    sentence = sentence_buffer[:end_idx].strip()
                    sentence_buffer = sentence_buffer[end_idx:]

                    if sentence:
                        clean_partial_text = strip_action_tag(full_response_acc).strip()
                        await safe_send_json({
                            "type": "transcription",
                            "role": "assistant",
                            "text": clean_partial_text + "...",
                            "language": lang,
                        })
                        await safe_send_json({
                            "type": "neural_event",
                            "event": "AI_GENERATION_TOKEN",
                            "tokenCount": len(sentence.split()),
                            "timestamp": time.time(),
                        })
                        first_sentence_sent = True

                        # Clean sentence for TTS — pass resolved emotion label
                        tts_sentence = clean_for_tts(sentence)
                        # Safety guard: skip if ACTION tag content still leaks through
                        if tts_sentence and 'tool' not in tts_sentence and '[ACTION' not in tts_sentence and 'summary\"' not in tts_sentence and 'params\"' not in tts_sentence:
                            print(f"[TTS CHUNK Arya] lang={lang} emotion={emotion_label} | {tts_sentence}")
                            audio_bytes, _ = await generate_audio_async(tts_sentence, lang, emotion_label)
                            if audio_bytes:
                                await safe_send_bytes(audio_bytes)

            # Process remaining buffer
            flushed = stream_filter.flush()
            if flushed:
                sentence_buffer += flushed

            if sentence_buffer.strip():
                sentence = sentence_buffer.strip()

                if not first_sentence_sent:
                    clean_partial_text = strip_action_tag(full_response_acc).strip()
                    await safe_send_json({
                        "type": "transcription",
                        "role": "assistant",
                        "text": clean_partial_text + "...",
                        "language": lang,
                    })

                tts_sentence = clean_for_tts(sentence)
                # Safety guard: skip if ACTION tag content still leaks through
                if tts_sentence and 'tool' not in tts_sentence and '[ACTION' not in tts_sentence and 'summary"' not in tts_sentence and 'params"' not in tts_sentence:
                    print(f"[TTS CHUNK Arya] emotion={emotion_label} lang={lang} | {tts_sentence}")
                    audio_bytes, _ = await generate_audio_async(tts_sentence, lang, emotion_label)
                    if audio_bytes:
                        await safe_send_bytes(audio_bytes)


            # ── Execute [ACTION:{...}] tool if present ─────────────────
            action_data = extract_action(full_response_acc)
            if action_data:
                tool_name = action_data.get("tool", "")
                tool_params = action_data.get("params", {})

                await safe_send_json({
                    "type": "neural_event",
                    "event": "TOOL_STARTED",
                    "toolName": tool_name,
                    "params": tool_params,
                    "timestamp": time.time(),
                })

                print(f"[TOOL] Executing: {tool_name} params={tool_params}")
                result = execute_tool(tool_name, tool_params)
                print(f"[TOOL] Result: {result}")

                if result.get("requires_confirmation"):
                    await safe_send_json({
                        "type": "tool_confirm",
                        "tool": tool_name,
                        "action_id": result.get("action_id"),
                        "confirmation_type": result.get("confirmation_type"),
                        "prompt": result.get("confirmation_prompt"),
                        "summary": result.get("message"),
                        "target": result.get("target_summary"),
                    })
                elif result.get("security_alert"):
                    await safe_send_json({
                        "type": "security_alert",
                        "tool": tool_name,
                        "message": result.get("message"),
                        "timestamp": time.time(),
                    })
                    await safe_send_json({
                        "type": "tool_result",
                        "tool": tool_name,
                        "success": False,
                        "message": result.get("message", ""),
                    })
                    await safe_send_json({
                        "type": "neural_event",
                        "event": "TOOL_COMPLETED",
                        "toolName": tool_name,
                        "success": False,
                        "message": result.get("message", ""),
                        "timestamp": time.time(),
                    })
                else:
                    is_ok = result.get("success", False)
                    res_msg = result.get("message", "")
                    await safe_send_json({
                        "type": "tool_result",
                        "tool": tool_name,
                        "success": is_ok,
                        "message": res_msg,
                        "confirmation": result.get("confirmation"),
                    })
                    await safe_send_json({
                        "type": "neural_event",
                        "event": "TOOL_COMPLETED",
                        "toolName": tool_name,
                        "success": is_ok,
                        "message": res_msg,
                        "confirmation": result.get("confirmation"),
                        "timestamp": time.time(),
                    })

                    # If tool failed after optimistic text was spoken, speak the specific failure reason
                    if not is_ok and res_msg and not result.get("requires_confirmation"):
                        failure_tts = clean_for_tts(res_msg)
                        if failure_tts:
                            print(f"[TTS CHUNK Failure Feedback] {failure_tts}")
                            audio_bytes, _ = await generate_audio_async(failure_tts, lang, "concerned")
                            if audio_bytes:
                                await safe_send_bytes(audio_bytes)


            # Final transcription message with clean text
            if full_response_acc:
                clean_full_text = clean_llm_output(full_response_acc)
                # If tool failed, append specific diagnostic message to chat transcription
                if action_data and result and not result.get("success") and result.get("message"):
                    if not result.get("requires_confirmation") and not result.get("security_alert"):
                        clean_full_text += f"\n\n⚠️ {result.get('message')}"

                await safe_send_json({
                    "type": "transcription",
                    "role": "assistant",
                    "text": clean_full_text,
                    "emotion": emotion_label or "neutral",
                    "language": lang,
                })

                # ── Persist Conversation History Turn (SQLite & Redis) ──────────
                if u_text and not skip_memory:
                    try:
                        from llm_agent import save_chat_history
                        db.save_turn(memory_id, "avatar.vrm", "user", u_text)
                        db.save_turn(memory_id, "avatar.vrm", "assistant", clean_full_text, emotion=emotion_label or "neutral")
                        history_snap.append({"role": "user", "content": u_text})
                        history_snap.append({"role": "assistant", "content": clean_full_text})
                        save_chat_history(memory_id, "avatar.vrm", history_snap)
                        print(f"[Memory] Persistent turn saved for session {memory_id} (total turns: {len(history_snap)})")
                    except Exception as _save_err:
                        print(f"[Memory WARNING] Failed to persist session turn: {_save_err}")

            await safe_send_json({
                "type": "neural_event",
                "event": "AI_COMPLETED",
                "timestamp": time.time(),
            })

        except asyncio.CancelledError:
            stop_event.set()
            print(f"[INFO] Response cancelled for session {session_id} (barge-in or disconnect)")
            raise

    # Background worker to process queued messages sequentially
    async def session_worker():
        nonlocal current_processing_task
        while True:
            try:
                args = await task_queue.get()
                if args is None:
                    break
                user_txt, lang, whisp_dur, is_intro = args
                
                # Start processing the single message
                current_processing_task = asyncio.create_task(
                    process_response(user_txt, lang, whisp_dur, is_intro)
                )
                try:
                    await current_processing_task
                except asyncio.CancelledError:
                    pass
                finally:
                    current_processing_task = None
                    task_queue.task_done()
            except Exception as err:
                print(f"[WORKER ERROR] {err}")

    worker_task = asyncio.create_task(session_worker())

    try:
        while True:
            # ── STEP 1: Receive data (Audio PCM or Text JSON) ──────────────
            try:
                message = await websocket.receive()
            except RuntimeError as e:
                if "disconnect" in str(e).lower():
                    print(f"\n[INFO] Client disconnected cleanly (RuntimeError). Session {session_id} ended.")
                    break
                raise
            
            if message.get("type") == "websocket.disconnect":
                print(f"\n[INFO] Client disconnected cleanly. Session {session_id} ended.")
                break

            user_text = ""
            detected_lang = "en"
            is_audio_input = False
            is_intro_trigger = False

            if "bytes" in message:
                is_audio_input = True
                data = message["bytes"]
                t_whisp_start = time.time()
                expected_lang = SESSION_LANGUAGES.get(session_id, "en")
                result = await asyncio.to_thread(
                    transcriber.process_audio_chunk, data, expected_lang
                )
                whisper_duration = time.time() - t_whisp_start
                if not result or not result.get("text"):
                    continue
                user_text     = result["text"]
                detected_lang = result["language"]
                # ── Hinglish detection: if Devanagari chars mixed with Latin → hinglish
                import unicodedata as _ud
                _has_deva = any(_ud.name(c, "").startswith("DEVANAGARI") for c in user_text if c.isalpha())
                _has_latin = any("LATIN" in _ud.name(c, "") for c in user_text if c.isalpha())
                if _has_deva and _has_latin:
                    detected_lang = "hinglish"
                elif detected_lang not in ("hi", "en", "hinglish"):
                    # If Whisper detected something unexpected for short clips, trust hi as session default
                    session_default = SESSION_LANGUAGES.get(session_id, "en")
                    if session_default == "hi" and len(user_text.split()) < 8:
                        detected_lang = "hi"
                print(f"\n[STEP 2] Whisper [{detected_lang}]: '{user_text}' (took {whisper_duration:.2f}s)")
            elif "text" in message:
                import json
                try:
                    payload = json.loads(message["text"])
                    if payload.get("type") == "text_input":
                        user_text = payload.get("text")
                        detected_lang = payload.get("language", SESSION_LANGUAGES.get(session_id, "en"))
                        if "user_id" in payload:
                            SESSION_USER_IDS[session_id] = payload["user_id"]
                            effective_user_id = payload["user_id"]
                        if "selected_doc_ids" in payload:
                            SESSION_SELECTED_DOCS[session_id] = payload["selected_doc_ids"]
                            SESSION_SELECTED_DOCS[effective_user_id] = payload["selected_doc_ids"]
                        print(f"\n[TEXT INPUT]: '{user_text}'")
                        whisper_duration = 0.0
                    elif payload.get("type") == "update_selected_docs":
                        docs = payload.get("selected_doc_ids")
                        SESSION_SELECTED_DOCS[session_id] = docs
                        if "user_id" in payload:
                            SESSION_SELECTED_DOCS[payload["user_id"]] = docs
                        print(f"[RAG] Active document selection updated: {docs}")
                        continue
                    elif payload.get("type") == "config_update":
                        if "user_id" in payload:
                            uid = payload["user_id"]
                            SESSION_USER_IDS[session_id] = uid
                            effective_user_id = uid
                            print(f"[CONFIG] User identity set: {uid}")

                        if "language" in payload:
                            lang = payload.get("language")
                            SESSION_LANGUAGES[session_id] = lang
                            print(f"\n[CONFIG] Language changed to: {lang}")

                        if "mode" in payload:
                            new_mode = payload.get("mode", "gf").lower()
                            if new_mode in ("gf", "assistant"):
                                SESSION_MODES[session_id] = new_mode
                                print(f"[MODE] Config update → {new_mode} mode for session {session_id}")
                                await safe_send_json({"type": "mode_changed", "mode": new_mode})

                        if "vad_sensitivity" in payload:
                            sens = payload.get("vad_sensitivity")
                            transcriber.set_sensitivity(sens)
                        continue
                    elif payload.get("type") == "intro_trigger":
                        user_text = payload.get("text")
                        detected_lang = payload.get("language", SESSION_LANGUAGES.get(session_id, "en"))
                        if "user_id" in payload:
                            SESSION_USER_IDS[session_id] = payload["user_id"]
                            effective_user_id = payload["user_id"]
                        
                        from llm_agent import get_chat_history
                        history = get_chat_history(effective_user_id, "avatar.vrm")
                        
                        if len(history) > 0:
                            is_intro_trigger = True
                            user_text = "(Greet me as a returning user, casually in Hindi/Hinglish.)"
                            print(f"\n[INTRO TRIGGER] Skipped full intro for avatar.vrm, doing short welcome back.")
                        else:
                            is_intro_trigger = True
                            print(f"\n[INTRO TRIGGER] Full intro for avatar.vrm")
                        whisper_duration = 0.0
                    else:
                        continue
                except Exception as e:
                    print(f"[WS] Error parsing text message: {e}")
                    continue
            else:
                continue

            if not user_text:
                continue

            # ── Check for Memory Reset Command ─────────────────────────────────────
            reset_commands = ["apni memory clear karo", "clear memory", "forget everything", "meri baatein bhul jao", "sab kuch bhul jao", "memory delete karo"]
            clean_input = user_text.lower().strip()
            if any(cmd in clean_input for cmd in reset_commands):
                print(f"[INFO] User requested memory reset for user={effective_user_id}")
                db.clear_history(effective_user_id)
                from llm_agent import redis_client as _rc
                if _rc:
                    try:
                        for key in _rc.scan_iter(f"chat_history:{effective_user_id}*"):
                            _rc.delete(key)
                    except Exception as _re:
                        print(f"[Redis] clear error: {_re}")

                reset_msg = "Maine apni saari purani memory delete kar di hai, ek fresh start ke liye!"
                await websocket.send_json({
                    "type": "transcription",
                    "role": "assistant",
                    "text": reset_msg,
                    "emotion": "happy",
                    "language": detected_lang,
                })
                
                f_audio, f_visemes = await generate_audio_async(reset_msg, detected_lang, "happy", "avatar.vrm")
                if f_visemes: await websocket.send_json({"type": "visemes", "data": f_visemes})
                if f_audio: await websocket.send_bytes(f_audio)
                continue
            # ───────────────────────────────────────────────────────────────────────

            # ── BARGE-IN & QUEUEING LOGIC ─────────────────────────────────────────
            if is_audio_input:
                if current_processing_task and not current_processing_task.done():
                    print(f"[BARGE-IN] Voice interruption detected! Cancelling current response.")
                    current_processing_task.cancel()
                    while not task_queue.empty():
                        try:
                            task_queue.get_nowait()
                            task_queue.task_done()
                        except asyncio.QueueEmpty:
                            break

                await websocket.send_json({
                    "type": "transcription",
                    "role": "user",
                    "text": user_text,
                    "language": detected_lang,
                })
                await task_queue.put((user_text, detected_lang, whisper_duration, is_intro_trigger))

            else:
                print(f"[QUEUE] Added text question to queue.")
                await task_queue.put((user_text, detected_lang, whisper_duration, is_intro_trigger))

    except WebSocketDisconnect:
        print(f"\n[INFO] Client disconnected cleanly (Exception). Session {session_id} ended.")
    except Exception as e:
        print(f"\n[ERROR] WebSocket error: {e}")
    finally:
        # Cleanup tasks
        if current_processing_task and not current_processing_task.done():
            current_processing_task.cancel()
        if worker_task and not worker_task.done():
            worker_task.cancel()


@app.get("/")
def read_root():
    return {"message": "3D Avatar Assistant API"}


if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        ws_ping_interval=60,   # Send keepalive ping every 60s (default: 20s)
        ws_ping_timeout=120,   # Allow 120s before timing out (default: 20s)
    )
