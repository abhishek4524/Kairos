from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Depends, Header, HTTPException, status
import os
import uvicorn
import asyncio
import uuid
import re
import time
import warnings

warnings.filterwarnings("ignore", category=FutureWarning)
warnings.filterwarnings("ignore", category=UserWarning)

from transcriber import RealTimeTranscriber
from llm_agent import generate_streaming_response
from tts_agent import generate_audio_async
import db

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

SESSION_AVATARS = {}
SESSION_LANGUAGES = {}
SESSION_USER_IDS = {}  # session_id -> nanban_user_id (browser-local anonymous ID)

app = FastAPI()

allowed_origins_env = os.getenv("ALLOWED_ORIGINS", "")
if allowed_origins_env:
    allowed_origins = [origin.strip() for origin in allowed_origins_env.split(",") if origin.strip()]
else:
    allowed_origins = ["*"]  # Fallback for local dev

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

db.init_db()

@app.get("/api/sessions")
def get_sessions(user_id: str = ""):
    return db.get_all_sessions(user_id=user_id if user_id else None)

@app.get("/api/history/{session_id}")
def get_history(session_id: str):
    return db.get_session_history(session_id)

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
    r'|sharedFocus|openPosture)\]?[:\s]*',
    re.IGNORECASE
)

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
                expected_lang = SESSION_LANGUAGES.get(session_id, "en")
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
                        if "avatar" in payload:
                            avatar_file = payload.get("avatar")
                            old_avatar  = SESSION_AVATARS.get(session_id)
                            SESSION_AVATARS[session_id] = avatar_file
                            if old_avatar and old_avatar != avatar_file:
                                print(f"[CONFIG] Avatar switched from {old_avatar} to {avatar_file}. Loading new context.")
                        if "language" in payload:
                            lang = payload.get("language")
                            SESSION_LANGUAGES[session_id] = lang
                            print(f"\n[CONFIG] Language changed to: {lang}")
                        continue
                    elif payload.get("type") == "intro_trigger":
                        user_text = payload.get("text")
                        detected_lang = payload.get("language", "en")
                        # Honour user_id if sent with this payload
                        if "user_id" in payload:
                            SESSION_USER_IDS[session_id] = payload["user_id"]
                            effective_user_id = payload["user_id"]
                        
                        from llm_agent import get_chat_history
                        current_avatar = SESSION_AVATARS.get(session_id, "avatar.vrm")
                        history = get_chat_history(effective_user_id, current_avatar)
                        
                        if len(history) > 0:
                            print(f"\n[INTRO TRIGGER] Skipped full intro for {current_avatar}, doing short welcome back.")
                            user_text = "Say a very short 1-line welcome back or acknowledgment that you are listening. Do NOT introduce yourself."
                        else:
                            print(f"\n[INTRO TRIGGER] Full intro for {current_avatar}")
                            
                        whisper_duration = 0.0
                        is_intro_trigger = True
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
                from llm_agent import redis_client
                for key in redis_client.scan_iter(f"chat_history:{effective_user_id}*"):
                    redis_client.delete(key)
                
                reset_msg = "Maine apni saari purani memory delete kar di hai, ek fresh start ke liye!"
                await websocket.send_json({
                    "type": "transcription",
                    "role": "assistant",
                    "text": reset_msg,
                    "emotion": "happy",
                    "language": detected_lang,
                })
                
                current_avatar = SESSION_AVATARS.get(session_id, "avatar.vrm")
                f_audio, f_visemes = await generate_audio_async(reset_msg, detected_lang, "happy", current_avatar)
                if f_visemes: await websocket.send_json({"type": "visemes", "data": f_visemes})
                if f_audio: await websocket.send_bytes(f_audio)
                continue
            # ───────────────────────────────────────────────────────────────────────

            # ── BARGE-IN & QUEUEING LOGIC ─────────────────────────────────────────
            # If voice input and speech sustained, it's an interruption -> cancel current & clear queue
            if is_audio_input:
                if current_processing_task and not current_processing_task.done():
                    if transcriber.get_speech_chunk_count() >= transcriber._bargeIn_min_chunks:
                        print(f"[BARGE-IN] Voice interruption detected! Cancelling current response.")
                        current_processing_task.cancel()
                        # Clear any pending queued questions
                        while not task_queue.empty():
                            try:
                                task_queue.get_nowait()
                                task_queue.task_done()
                            except asyncio.QueueEmpty:
                                break
                    else:
                        print(f"[BARGE-IN] Debounced — only {transcriber.get_speech_chunk_count()} chunk(s). Ignoring noise.")
                        continue # Ignore this input completely

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
            async def process_response(u_text, lang, whisp_time, skip_memory=False):
                import re as _re
                import threading

                t_llm_start = time.time()
                print(f"[STEP 3] Calling Groq for session {session_id}...")

                current_avatar = SESSION_AVATARS.get(session_id, "avatar.vrm")

                sentence_end_re = _re.compile(r'([.!?\n]+)\s*')
                q = asyncio.Queue()
                loop = asyncio.get_running_loop()
                stop_event = threading.Event()

                # Use the persistent user identity for memory/history
                memory_id = SESSION_USER_IDS.get(session_id, session_id)

                def producer():
                    try:
                        for c in generate_streaming_response(
                            memory_id, u_text, current_avatar, lang, skip_memory=skip_memory
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

                        full_response_acc += chunk
                        sentence_buffer += chunk

                        # Parse emotion tag early
                        if emotion is None:
                            m = EMOTION_RE.match(full_response_acc)
                            if m:
                                raw_emotion = m.group(1).lower()
                                emotion = EMOTION_MAP.get(raw_emotion, "neutral")
                                sentence_buffer = EMOTION_RE.sub("", sentence_buffer)
                            elif len(full_response_acc) > 40 and "[" not in full_response_acc:
                                from llm_agent import AVATAR_CONFIG as _AV_CFG
                                emotion = _AV_CFG.get(current_avatar, {}).get("default_emotion", "neutral")

                        if emotion is not None:
                            match = sentence_end_re.search(sentence_buffer)
                            if match:
                                end_idx = match.end()
                                sentence = sentence_buffer[:end_idx].strip()
                                sentence_buffer = sentence_buffer[end_idx:]

                                if sentence:
                                    # Mid-stream update: send accumulated text so far with "..."
                                    clean_partial_text = EMOTION_RE.sub("", full_response_acc).strip()
                                    await safe_send_json({
                                        "type": "transcription",
                                        "role": "assistant",
                                        "text": clean_partial_text + "...",
                                        "emotion": emotion or "neutral",
                                        "language": lang,
                                    })
                                    first_sentence_sent = True

                                    print(f"[TTS CHUNK] {sentence}")
                                    audio_bytes, visemes = await generate_audio_async(sentence, lang, emotion, current_avatar)
                                    if visemes:
                                        await safe_send_json({"type": "visemes", "data": visemes})
                                    if audio_bytes:
                                        await safe_send_bytes(audio_bytes)

                    # Process remaining buffer
                    if sentence_buffer.strip():
                        sentence = sentence_buffer.strip()
                        if not emotion:
                            from llm_agent import AVATAR_CONFIG as _AV_CFG
                            emotion = _AV_CFG.get(current_avatar, {}).get("default_emotion", "neutral")

                        if not first_sentence_sent:
                            clean_partial_text = EMOTION_RE.sub("", full_response_acc).strip()
                            await safe_send_json({
                                "type": "transcription",
                                "role": "assistant",
                                "text": clean_partial_text + "...",
                                "emotion": emotion or "neutral",
                                "language": lang,
                            })

                        print(f"[TTS CHUNK] {sentence}")
                        audio_bytes, visemes = await generate_audio_async(sentence, lang, emotion, current_avatar)
                        if visemes:
                            await safe_send_json({"type": "visemes", "data": visemes})
                        if audio_bytes:
                            await safe_send_bytes(audio_bytes)

                    # ONE final transcription message with the complete clean text
                    if full_response_acc:
                        clean_full_text = EMOTION_RE.sub("", full_response_acc).strip()
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
