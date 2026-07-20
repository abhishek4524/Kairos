from fastapi import FastAPI, WebSocket, WebSocketDisconnect
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

from fastapi.middleware.cors import CORSMiddleware

SESSION_AVATARS = {}
SESSION_LANGUAGES = {}

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

db.init_db()

@app.get("/api/sessions")
def get_sessions():
    return db.get_all_sessions()

@app.get("/api/history/{session_id}")
def get_history(session_id: str):
    return db.get_session_history(session_id)

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

    active_task = None

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
                        print(f"\n[TEXT INPUT]: '{user_text}'")
                        whisper_duration = 0.0
                    elif payload.get("type") == "config_update":
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
                        
                        from llm_agent import get_chat_history
                        current_avatar = SESSION_AVATARS.get(session_id, "avatar.vrm")
                        history = get_chat_history(session_id, current_avatar)
                        
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
                print(f"[INFO] User requested memory reset for {session_id}")
                db.clear_history(session_id)
                from llm_agent import redis_client
                for key in redis_client.scan_iter(f"chat_history:{session_id}*"):
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

            # User spoke! Cancel any ongoing generation/TTS task (BARGE-IN)
            if active_task and not active_task.done():
                print(f"[BARGE-IN] Cancelling previous response for session {session_id}")
                active_task.cancel()

            if is_audio_input:
                await websocket.send_json({
                    "type": "transcription",
                    "role": "user",
                    "text": user_text,
                    "language": detected_lang,
                })

            # Define background generation task
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

                def producer():
                    try:
                        for c in generate_streaming_response(
                            session_id, u_text, current_avatar, lang, skip_memory=skip_memory
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
                                    if not first_sentence_sent:
                                        clean_full_text = EMOTION_RE.sub("", full_response_acc).strip()
                                        await safe_send_json({
                                            "type": "transcription",
                                            "role": "assistant",
                                            "text": clean_full_text + "...",
                                            "emotion": emotion,
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
                            clean_full_text = EMOTION_RE.sub("", full_response_acc).strip()
                            await safe_send_json({
                                "type": "transcription",
                                "role": "assistant",
                                "text": clean_full_text,
                                "emotion": emotion,
                                "language": lang,
                            })

                        print(f"[TTS CHUNK] {sentence}")
                        audio_bytes, visemes = await generate_audio_async(sentence, lang, emotion, current_avatar)
                        if visemes:
                            await safe_send_json({"type": "visemes", "data": visemes})
                        if audio_bytes:
                            await safe_send_bytes(audio_bytes)

                    # Final UI update with full clean text
                    if full_response_acc:
                        clean_full_text = EMOTION_RE.sub("", full_response_acc).strip()
                        await safe_send_json({
                            "type": "transcription",
                            "role": "assistant",
                            "text": clean_full_text,
                            "emotion": emotion,
                            "language": lang,
                        })

                except asyncio.CancelledError:
                    # Barge-in or disconnect: stop the producer thread and re-raise
                    stop_event.set()
                    print(f"[INFO] Response cancelled for session {session_id} (barge-in or disconnect)")
                    raise  # Re-raise so the outer task knows it was cancelled

            # Start the generation task
            active_task = asyncio.create_task(
                process_response(user_text, detected_lang, whisper_duration, is_intro_trigger)
            )


    except WebSocketDisconnect:
        print(f"\n[INFO] Client disconnected cleanly (Exception). Session {session_id} ended.")
    except Exception as e:
        print(f"\n[ERROR] WebSocket error: {e}")
    finally:
        if active_task and not active_task.done():
            active_task.cancel()


@app.get("/")
def read_root():
    return {"message": "3D Avatar Assistant API"}


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
