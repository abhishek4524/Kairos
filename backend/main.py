from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Depends, Header, HTTPException, status
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
from llm_agent import generate_streaming_response, clean_llm_output
from tts_agent import generate_audio_async
import db
import memory_store
import document_pipeline
from agent_tools.executor import execute_tool, extract_action, strip_action_tag

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

app = FastAPI()

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

@app.get("/api/history/{session_id}")
def get_history(session_id: str):
    return db.get_session_history(session_id)

@app.delete("/api/history/{session_id}")
def delete_history_session(session_id: str):
    """Delete a single session from chat history."""
    db.clear_history(session_id)
    return {"success": True, "deleted_session": session_id}

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

@app.post("/api/memory/ingest")
async def ingest_document(user_id: str, file: UploadFile = File(...)):
    """Upload and ingest a PDF, TXT, or MD file into long-term memory."""
    ext = pathlib.Path(file.filename).suffix.lower()
    if ext not in (".pdf", ".txt", ".md"):
        raise HTTPException(status_code=400, detail="Only .pdf, .txt, and .md files are supported")

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
    text = strip_action_tag(text)
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

    # The effective identity for memory/history. Defaults to session_id if
    # the frontend hasn't sent a user_id yet (backward-compatible).
    effective_user_id = session_id

    task_queue = asyncio.Queue()
    current_processing_task = None

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
                # ── STEP 2: Whisper STT (run in thread so event loop stays free) ─
                t_whisp_start = time.time()
                expected_lang = SESSION_LANGUAGES.get(session_id, "auto")
                # BUG-1 FIX: process_audio_chunk is CPU-bound (Whisper); run in
                # a thread pool so we never block the async event loop.
                result = await asyncio.to_thread(
                    transcriber.process_audio_chunk, data, expected_lang
                )
                whisper_duration = time.time() - t_whisp_start
                if not result or not result.get("text"):
                    continue
                user_text     = result["text"]
                detected_lang = result["language"]
                print(f"\n[STEP 2] Whisper [{detected_lang}]: '{user_text}' (took {whisper_duration:.2f}s)")
            elif "text" in message:
                import json
                try:
                    payload = json.loads(message["text"])
                    if payload.get("type") == "text_input":
                        user_text = payload.get("text")
                        detected_lang = payload.get("language", "en")
                        # Honour user_id if sent with this payload
                        if "user_id" in payload:
                            SESSION_USER_IDS[session_id] = payload["user_id"]
                            effective_user_id = payload["user_id"]
                        print(f"\n[TEXT INPUT]: '{user_text}'")
                        whisper_duration = 0.0
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

                        if "vad_sensitivity" in payload:
                            sens = payload.get("vad_sensitivity")
                            transcriber.set_sensitivity(sens)
                        continue
                    elif payload.get("type") == "intro_trigger":
                        user_text = payload.get("text")
                        detected_lang = payload.get("language", "en")
                        # Honour user_id if sent with this payload
                        if "user_id" in payload:
                            SESSION_USER_IDS[session_id] = payload["user_id"]
                            effective_user_id = payload["user_id"]
                        
                        from llm_agent import get_chat_history
                        history = get_chat_history(effective_user_id, "avatar.vrm")
                        
                        if len(history) > 0:
                            is_intro_trigger = True
                            user_text = "(Greet me as a returning user, casually.)"
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
            # If voice input and speech sustained, it's an interruption -> cancel current & clear queue
            if is_audio_input:
                if current_processing_task and not current_processing_task.done():
                    print(f"[BARGE-IN] Voice interruption detected! Cancelling current response.")
                    current_processing_task.cancel()
                    # Clear any pending queued questions
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
                # Add to queue
                await task_queue.put((user_text, detected_lang, whisper_duration, is_intro_trigger))

            else:
                # Text input -> Queue sequentially, do not barge-in. Answers multiple text questions one-by-one.
                print(f"[QUEUE] Added text question to queue.")
                await task_queue.put((user_text, detected_lang, whisper_duration, is_intro_trigger))

            # Define background generation task (used by the worker)
            async def process_response(u_text, lang, whisp_dur, is_intro):
                import re as _re
                import threading

                t_llm_start = time.time()
                print(f"[STEP 3] Calling Groq for session {session_id}...")

                skip_memory = is_intro
                memory_id = effective_user_id
                
                await websocket.send_json({"type": "status", "status": "Thinking"})

                sentence_end_re = _re.compile(r'([.!?\n]+)\s*')
                q = asyncio.Queue()
                loop = asyncio.get_running_loop()
                stop_event = threading.Event()

                def producer():
                    try:
                        for c in generate_streaming_response(
                            memory_id, u_text, "avatar.vrm", lang,
                            skip_memory=skip_memory,
                            user_id=effective_user_id,
                        ):
                            if stop_event.is_set():
                                break
                            asyncio.run_coroutine_threadsafe(q.put(c), loop)
                    except Exception as prod_err:
                        print(f"[PRODUCER ERROR] {prod_err}")
                    finally:
                        asyncio.run_coroutine_threadsafe(q.put(None), loop)

                threading.Thread(target=producer, daemon=True).start()

                sentence_buffer = ""
                full_response_acc = ""
                emotion = None
                first_sentence_sent = False
                # groq/compound outputs a **Reasoning**...**Final Answer** preamble.
                # We suppress it from TTS and the UI until the final answer starts.
                in_reasoning_block = False
                reasoning_done = False
                _FA_RE = _re.compile(r'\*{0,2}Final Answer\*{0,2}\s*\n?', _re.IGNORECASE)

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

                try:
                    while True:
                        chunk = await q.get()
                        if chunk is None:
                            break
                        if chunk.startswith("[Error") or chunk.startswith("[ERROR"):
                            print(chunk)
                            break

                        # ── Reasoning-block suppression ───────────────────────
                        if not reasoning_done:
                            full_response_acc += chunk
                            # Detect start of reasoning
                            if not in_reasoning_block and (
                                "**Reasoning**" in full_response_acc or
                                "<think>" in full_response_acc
                            ):
                                in_reasoning_block = True
                            # Detect end of reasoning — "**Final Answer**" marker
                            if in_reasoning_block:
                                fa_match = _FA_RE.search(full_response_acc)
                                if fa_match:
                                    reasoning_done = True
                                    in_reasoning_block = False
                                    # Reset acc to only what comes after the marker
                                    full_response_acc = full_response_acc[fa_match.end():]
                                    sentence_buffer = full_response_acc
                                # Still inside reasoning block — skip this chunk for TTS
                                continue
                            # No reasoning block started — treat as plain output
                            reasoning_done = True  # not a CoT model response, stream normally
                            sentence_buffer = full_response_acc
                        else:
                            full_response_acc += chunk
                            sentence_buffer += chunk

                        # Parse emotion tag early from the leading gesture tag
                        if emotion is None:
                            m = EMOTION_RE.match(full_response_acc)
                            if m:
                                raw_emotion = m.group(1).lower()
                                emotion = EMOTION_MAP.get(raw_emotion, "neutral")
                                sentence_buffer = EMOTION_RE.sub("", sentence_buffer)
                            # Note: removed premature comforting fallback —
                            # emotion stays None until a real tag arrives.
                            # If no tag arrives by stream end, we default below.

                        # Strip [ACTION:{...}] and ALL mid-response gesture tags from TTS buffer
                        sentence_buffer = strip_action_tag(sentence_buffer)
                        sentence_buffer = ALL_GESTURE_RE.sub("", sentence_buffer)

                        if emotion is not None:
                            match = sentence_end_re.search(sentence_buffer)
                            if match:
                                end_idx = match.end()
                                sentence = sentence_buffer[:end_idx].strip()
                                sentence_buffer = sentence_buffer[end_idx:]

                                if sentence:
                                    # Clean for chat display
                                    clean_partial_text = ALL_GESTURE_RE.sub("", EMOTION_RE.sub("", full_response_acc)).strip()
                                    clean_partial_text = strip_action_tag(clean_partial_text)
                                    await safe_send_json({
                                        "type": "transcription",
                                        "role": "assistant",
                                        "text": clean_partial_text + "...",
                                        "emotion": emotion or "neutral",
                                        "language": lang,
                                    })
                                    first_sentence_sent = True

                                    # Clean sentence for TTS (strips all tags, symbols, and code blocks)
                                    tts_sentence = clean_for_tts(sentence)
                                    if tts_sentence:
                                        print(f"[TTS CHUNK] emotion={emotion} | {tts_sentence}")
                                        audio_bytes, visemes = await generate_audio_async(tts_sentence, "en", emotion or "neutral", "avatar.vrm")
                                        if visemes:
                                            await safe_send_json({"type": "visemes", "data": visemes})
                                        if audio_bytes:
                                            await safe_send_bytes(audio_bytes)

                    # Process remaining buffer
                    if sentence_buffer.strip():
                        sentence = sentence_buffer.strip()
                        if not emotion:
                            emotion = "neutral"  # default — no fake comforting

                        if not first_sentence_sent:
                            clean_partial_text = ALL_GESTURE_RE.sub("", EMOTION_RE.sub("", full_response_acc)).strip()
                            clean_partial_text = strip_action_tag(clean_partial_text)
                            await safe_send_json({
                                "type": "transcription",
                                "role": "assistant",
                                "text": clean_partial_text + "...",
                                "emotion": emotion or "neutral",
                                "language": lang,
                            })

                        tts_sentence = clean_for_tts(sentence)
                        if tts_sentence:
                            print(f"[TTS CHUNK] emotion={emotion} | {tts_sentence}")
                            audio_bytes, visemes = await generate_audio_async(tts_sentence, "en", emotion or "neutral", "avatar.vrm")
                            if visemes:
                                await safe_send_json({"type": "visemes", "data": visemes})
                            if audio_bytes:
                                await safe_send_bytes(audio_bytes)

                    # ── Execute [ACTION:{...}] tool if present ─────────────────
                    action_data = extract_action(full_response_acc)
                    if action_data:
                        tool_name = action_data.get("tool", "")
                        tool_params = action_data.get("params", {})
                        is_sensitive_tool = tool_name == "check_whatsapp_notifications"

                        if not is_sensitive_tool:
                            print(f"[TOOL] Executing: {tool_name} params={tool_params}")
                            result = execute_tool(tool_name, tool_params)
                            print(f"[TOOL] Result: {result}")
                            # Notify frontend of execution result
                            await safe_send_json({
                                "type": "tool_result",
                                "tool": tool_name,
                                "success": result["success"],
                                "message": result["message"],
                            })
                        else:
                            # Sensitive tool — ask frontend for confirmation
                            await safe_send_json({
                                "type": "tool_confirm",
                                "tool": tool_name,
                                "params": tool_params,
                                "summary": action_data.get("summary", f"Execute {tool_name}"),
                            })

                    # ONE final transcription message with the complete clean text
                    if full_response_acc:
                        clean_full_text = clean_llm_output(full_response_acc)
                        await safe_send_json({
                            "type": "transcription",
                            "role": "assistant",
                            "text": clean_full_text,
                            "emotion": emotion or "neutral",
                            "language": lang,
                        })

                except asyncio.CancelledError:
                    # Barge-in or disconnect: stop the producer thread and re-raise
                    stop_event.set()
                    print(f"[INFO] Response cancelled for session {session_id} (barge-in or disconnect)")
                    raise  # Re-raise so the outer task knows it was cancelled


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
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
