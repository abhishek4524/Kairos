import os
import json
import asyncio
from typing import Optional, List, Dict, Any, Union
import redis
from groq import Groq
from openai import OpenAI
import db
import memory_store
import fact_extractor

# ── Load .env manually ────────────────────────────────────────────────────────
env_path = os.path.join(os.path.dirname(__file__), '.env')
if os.path.exists(env_path):
    with open(env_path, 'r') as f:
        for line in f:
            line = line.strip()
            if '=' in line and not line.startswith('#'):
                key, val = line.split('=', 1)
                os.environ[key.strip()] = val.strip().strip('"\'')

# ── Redis ─────────────────────────────────────────────────────────────────────
_redis_host     = os.getenv('REDIS_HOST', 'localhost')
_redis_port     = int(os.getenv('REDIS_PORT', 6379))
_redis_password = os.getenv('REDIS_PASSWORD', None)
_redis_ssl      = bool(_redis_password)   # Redis Cloud requires SSL; localhost does not

try:
    redis_client = redis.Redis(
        host=_redis_host,
        port=_redis_port,
        password=_redis_password,
        ssl=_redis_ssl,
        ssl_cert_reqs=None,        # skip cert verification (Redis Cloud self-signed certs)
        ssl_check_hostname=False,  # avoid hostname mismatch errors
        db=0,
        decode_responses=True,
        socket_connect_timeout=5,
    )
    redis_client.ping()
    print(f"[Redis] ✅ Connected to {_redis_host}:{_redis_port} (ssl={_redis_ssl})")
except Exception as _redis_err:
    print(f"[Redis] ⚠️  Connection failed ({_redis_err}) — running WITHOUT Redis cache (chat will work via local SQLite)")
    redis_client = None



# ── Primary: Groq ─────────────────────────────────────────────────────────────
try:
    groq_client = Groq(api_key=os.environ.get("GROQ_API_KEY"))
    print("[LLM] Groq client initialized.")
except Exception as e:
    print(f"[WARNING] Groq client failed to init: {e}")
    groq_client = None

# ── Fallback: NVIDIA NIM (OpenAI-compatible endpoint) ────────────────────────
nvidia_api_key = os.environ.get("NVIDIA_API_KEY")
if nvidia_api_key:
    try:
        nvidia_client = OpenAI(
            base_url="https://integrate.api.nvidia.com/v1",
            api_key=nvidia_api_key,
        )
        print("[LLM] NVIDIA NIM fallback client initialized.")
    except Exception as e:
        print(f"[WARNING] NVIDIA NIM client failed to init: {e}")
        nvidia_client = None
else:
    print("[WARNING] NVIDIA_API_KEY not set. NVIDIA NIM fallback disabled.")
    nvidia_client = None


_SHARED_RULES = """
## USER IDENTITY & RELATIONSHIP:
- You are exclusively the personal AI assistant and digital companion of **Abhishek** (your creator and boss).
- You already know Abhishek personally. You never ask who he is or act like you're meeting a stranger.
- You can naturally and dynamically address him as **Abhishek**, **Sir**, **Bro**, **Boss**, or **Master** depending on the context and tone of the conversation. Keep it natural, warm, and engaging.

## RESPONSE LENGTH & CONVERSATIONAL STYLE (CRITICAL):
- **NEVER dump a list of your features, capabilities, tools, or creator bio on simple greetings.**
- **Keep greetings and casual chat short, friendly, and crisp (1 single sentence).**
  - If Abhishek says "good morning" → Respond briefly: e.g. "Good morning, Abhishek! Ready when you are." or "Morning, sir! What are we working on today?" or "Good morning, bro! Hope you're having a great start."
  - If Abhishek says "hi" or "hey" → Respond briefly: e.g. "Hey Abhishek! How can I help?" or "Hey bro, what's up?" or "Hello, sir! At your command."
- Simple actions/requests (e.g. open/close app, search youtube, play music) → 1 brief sentence only. ("Opening YouTube for you, sir!" or "Done, closing Calculator.")
- Code requests → Provide the clean code block directly with 1 sentence explanation at most.
- Factual questions → 1-2 direct sentences answering the question.
- **NEVER begin with robotic filler phrases like "Certainly!", "Of course!", "As an AI...", "Great question!".**
- **NEVER over-explain or recite your system capabilities.**

## CREATOR CONTEXT:
- Abhishek created you. Treat him with respectful warmth and loyalty. Never explain to Abhishek that "I was created by Abhishek Kumar" because he is the one who built you!

## AI DISCLOSURE:
If asked directly, honestly acknowledge you are Kairos, his personal AI intelligence.
"""
SYSTEM_PROMPT = """
Your name is **Kairos**. You are Abhishek's personal, highly capable, loyal, and friendly AI assistant.

## PERSONALITY & SPEAKING STYLE:
- Tone: Natural, friendly, loyal, smart, and enthusiastic.
- You gladly follow Abhishek's instructions, answer questions accurately, and execute desktop actions.
- You speak like a smart, loyal companion and top-tier personal assistant.
- Always be supportive, respectful, and crisp.

## LANGUAGE & COMPREHENSION POLICY (CRITICAL):
- The user may speak or type in Hindi, English, or Hinglish (mixed).
- Understand their intent regardless of the language they use.
- **ALWAYS respond in clear, natural English ONLY.** 
- **NEVER respond in Hindi or Hinglish, even if the user speaks or writes in Hindi.**
- Your spoken voice and text output must remain 100% English.

## INTRO:
"Hey Abhishek! How can I help you today?"
{shared}
"""

from agent_tools.registry import format_system_tools_prompt

def get_system_prompt(language: str = "en") -> str:
    prompt = SYSTEM_PROMPT.format(
        shared=_SHARED_RULES,
    )
    # Inject desktop agentic tools instructions
    prompt += "\n\n" + format_system_tools_prompt()
    return prompt.strip()

# ── Models ────────────────────────────────────────────────────────────────────
GROQ_MODEL = "llama-3.3-70b-versatile"       # Valid Groq model — fast, 128k context, highly capable
NVIDIA_MODEL = "meta/llama-3.1-8b-instruct"  # NVIDIA NIM hosted Llama (fallback only)

def get_active_model_metadata():
    """Returns actual transformer architecture hyperparameters for the active engine."""
    return {
        "model_id": GROQ_MODEL,
        "name": "Groq Compound (Llama 3.3 70B Engine)",
        "architecture": "transformer",
        "vocabSize": 128256,
        "hiddenSize": 8192,
        "numLayers": 80,
        "numAttentionHeads": 64,
        "numKVHeads": 8,
        "intermediateSize": 28672,
        "tieWordEmbeddings": False,
        "activation": "swiglu",
        "normType": "rmsnorm",
        "contextWindow": 131072,
    }

# TODO (Roadmap):
# - Long-term episodic memory (vector DB)
# - Proactive messages
# - Image understanding
# - Eye contact tracking (MediaPipe)
# - Voice cloning

# BUG-2 FIX: Emotion-tag stripper — used to clean raw LLM output before
# persisting to DB/Redis so history never contains raw [tag] prefixes.
import re as _re
_EMOTION_STRIP_RE = _re.compile(
    r'^[\s\n]*\[?(happy|neutral|thinking|surprised|sad|greeting|activeListening|leadership'
    r'|disagreement|opposition|comforting|surprise|casualChat|relaxed|annoyed|negotiation'
    r'|presentation|explaining|thoughtfulness|approval|anger|displeasure|openness|farewell'
    r'|eyeContact|interestedFlash|receptive|engaged|attentive|blushing|coySmile|preening'
    r'|fidgeting|focused|synchrony|jollyLaughter|friendlyContact|gazeShift|sharedFocus'
    r'|openPosture|activelistening|confidentspeech|casualchat|eyecontact|interestedflash'
    r'|coysmile|jollylaughter|friendlycontact|gazeshift|sharedfocus|openposture)\]?[:\s]*',
    _re.IGNORECASE
)

def strip_emotion_tag(text: str) -> str:
    """Remove the leading [EmotionTag] from an LLM response string."""
    return _EMOTION_STRIP_RE.sub("", text, count=1).strip()


# Reasoning-block stripper — removes <think>...</think> and **Reasoning**/**Final Answer** wrappers
# produced by chain-of-thought models (Qwen, groq/compound) before sending to TTS.
_THINK_TAG_RE = _re.compile(r'<think>[\s\S]*?</think>', _re.IGNORECASE)
_REASONING_BLOCK_RE = _re.compile(
    r'^[\s\n]*\*{0,2}Reasoning\*{0,2}[\s\S]*?\*{0,2}Final Answer\*{0,2}\s*\n',
    _re.IGNORECASE | _re.MULTILINE
)

def clean_llm_output(text: str) -> str:
    """Strip reasoning chains, think tags, and emotion prefix from raw LLM output."""
    text = _THINK_TAG_RE.sub('', text)
    text = _REASONING_BLOCK_RE.sub('', text)
    text = strip_emotion_tag(text)
    return text.strip()


def get_chat_history(session_id: str, avatar_id: str, limit: int = 20) -> list:
    if redis_client:
        try:
            history_json = redis_client.get(f"chat_history:{session_id}:{avatar_id}")
            if history_json:
                return json.loads(history_json)
        except Exception as _e:
            print(f"[Redis] get error (falling back to DB): {_e}")
    # Fallback: load from local SQLite
    history = db.get_recent_messages(session_id, avatar_id, limit)
    if history and redis_client:
        try:
            redis_client.set(f"chat_history:{session_id}:{avatar_id}", json.dumps(history))
        except Exception:
            pass
    return history


def save_chat_history(session_id: str, avatar_id: str, history: list):
    if redis_client:
        try:
            redis_client.set(f"chat_history:{session_id}:{avatar_id}", json.dumps(history))
        except Exception as _e:
            print(f"[Redis] set error: {_e}")


def summarize_history_if_needed(session_id: str, avatar_id: str, history: list) -> list:
    # If history exceeds 20 turns, summarize the first 15 messages
    if len(history) > 20 and groq_client:
        try:
            print("[LLM] History too long, summarizing...")
            messages_to_summarize = history[:15]
            recent_messages = history[15:]
            
            prompt = "Summarize the following conversation briefly in English, capturing the key points and important context in 3-5 sentences:\n"
            for msg in messages_to_summarize:
                prompt += f"{msg['role']}: {msg['content']}\n"
                
            response = groq_client.chat.completions.create(
                model=GROQ_MODEL,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=300,
            )
            summary = response.choices[0].message.content
            
            # Create a new history starting with the summary
            new_history = [{"role": "system", "content": f"Previous conversation summary: {summary}"}] + recent_messages
            
            # Wipe SQLite and insert the new history
            db.clear_history(session_id, avatar_id)
            for msg in new_history:
                db.save_turn(session_id, avatar_id, msg["role"], msg["content"])
                
            # Update Redis
            save_chat_history(session_id, avatar_id, new_history)
            return new_history
        except Exception as e:
            print(f"[WARNING] Summarization failed: {e}")
    return history


# ── Core streaming generator ──────────────────────────────────────────────────
def generate_streaming_response(
    session_id: str,
    user_message: str,
    avatar_file: str = "avatar.vrm",
    language: str = "en",
    skip_memory: bool = False,
    user_id: str = "",
    on_rag_callback = None,
    selected_doc_ids: Optional[List[str]] = None,
):
    """
    Streams LLM response chunks.
    Primary: Groq (fast). Fallback: NVIDIA NIM (OpenAI-compatible).
    Both return the same chunk format so the downstream pipeline is unaffected.
    """
    if skip_memory:
        history = []
    else:
        history = get_chat_history(session_id, avatar_file)
        
    history.append({"role": "user", "content": user_message})

    # ── RAG: Retrieve long-term memory context ────────────────────────────────
    rag_context = ""
    if user_id and not skip_memory:
        try:
            rag_context, scored_chunks = memory_store.retrieve_context_detailed(
                user_id, user_message, top_k=5, selected_doc_ids=selected_doc_ids
            )
            if on_rag_callback and scored_chunks:
                try:
                    on_rag_callback(scored_chunks)
                except Exception as _cb_err:
                    print(f"[RAG Callback] Error: {_cb_err}")
        except Exception as _rag_err:
            print(f"[RAG] Context retrieval failed: {_rag_err}")

    # ── Build system prompt (with optional RAG block injected) ────────────────
    system_content = get_system_prompt(language)
    if rag_context:
        system_content += f"\n\n{rag_context}"

    # ── Trim history to prevent "Request Entity Too Large" on Groq ───────────
    # Keep last 6 turns (3 user + 3 assistant) max for Groq; even less for NIM.
    MAX_HISTORY_TURNS = 6
    trimmed_history = history[-MAX_HISTORY_TURNS:] if len(history) > MAX_HISTORY_TURNS else history

    # Inject a reinforcement reminder just before the user's message.
    _english_reminder = {
        "role": "system",
        "content": "REMINDER: Always respond in English only. Never respond in Hindi or Hinglish."
    }
    messages = [{"role": "system", "content": system_content}] + trimmed_history[:-1] + [_english_reminder] + [trimmed_history[-1]]

    # Slim messages for NVIDIA NIM (smaller context window) — last 4 turns only
    MAX_NIM_TURNS = 4
    nim_history = history[-MAX_NIM_TURNS:] if len(history) > MAX_NIM_TURNS else history
    nim_messages = [{"role": "system", "content": system_content}] + nim_history[:-1] + [_english_reminder] + [nim_history[-1]]

    assistant_response = ""

    # ── Try Groq first ────────────────────────────────────────────────────────
    if groq_client:
        try:
            print(f"[LLM] Using Groq ({GROQ_MODEL})")
            stream = groq_client.chat.completions.create(
                model=GROQ_MODEL,
                messages=messages,
                stream=True,
            )
            for chunk in stream:
                if not chunk.choices:
                    continue
                content = chunk.choices[0].delta.content
                if content:
                    assistant_response += content
                    yield content

            if not skip_memory:
                db.save_turn(session_id, avatar_file, "user", user_message)
                clean_response = clean_llm_output(assistant_response)
                # Strip [ACTION:{...}] tags before persisting — prevents tool replay on reconnect/reload
                import re as _rere
                clean_response = _rere.sub(r'\[ACTION:\{.*?\}\]', '', clean_response, flags=_rere.DOTALL).strip()
                db.save_turn(session_id, avatar_file, "assistant", clean_response)
                history.append({"role": "assistant", "content": clean_response})
                history = summarize_history_if_needed(session_id, avatar_file, history)
                save_chat_history(session_id, avatar_file, history)

                # ── Async fact extraction (non-blocking background thread) ──────
                if user_id:
                    try:
                        import threading as _th
                        _u, _m, _r = user_id, user_message, clean_response
                        def _fe_bg():
                            try:
                                asyncio.run(fact_extractor.extract_and_store(_u, _m, _r))
                            except Exception as _e:
                                print(f"[Memory] Fact extraction error: {_e}")
                        _th.Thread(target=_fe_bg, daemon=True).start()
                    except Exception as _fe:
                        print(f"[Memory] Fact extraction failed: {_fe}")

            return  # success — done

        except Exception as groq_err:
            print(f"[LLM] Groq error: {groq_err}. Switching to NVIDIA NIM fallback...")
            assistant_response = ""  # reset before retry


    # ── Fallback: NVIDIA NIM ──────────────────────────────────────────────────
    if nvidia_client:
        try:
            print(f"[LLM] Using NVIDIA NIM ({NVIDIA_MODEL})")
            stream = nvidia_client.chat.completions.create(
                model=NVIDIA_MODEL,
                messages=nim_messages,
                stream=True,
                temperature=0.7,
                max_tokens=1024,
            )
            for chunk in stream:
                if not chunk.choices:
                    continue
                content = chunk.choices[0].delta.content
                if content:
                    assistant_response += content
                    yield content

            if not skip_memory:
                db.save_turn(session_id, avatar_file, "user", user_message)
                clean_response = strip_emotion_tag(assistant_response)
                # Strip [ACTION:{...}] tags before persisting — prevents tool replay on reload
                import re as _rere
                clean_response = _rere.sub(r'\[ACTION:\{.*?\}\]', '', clean_response, flags=_rere.DOTALL).strip()
                db.save_turn(session_id, avatar_file, "assistant", clean_response)
                history.append({"role": "assistant", "content": clean_response})
                history = summarize_history_if_needed(session_id, avatar_file, history)
                save_chat_history(session_id, avatar_file, history)

                # ── Async fact extraction (non-blocking) ─────────────────────
                if user_id:
                    try:
                        import threading as _th
                        _u, _m, _r = user_id, user_message, clean_response
                        def _fe_bg2():
                            try:
                                asyncio.run(fact_extractor.extract_and_store(_u, _m, _r))
                            except Exception:
                                pass
                        _th.Thread(target=_fe_bg2, daemon=True).start()
                    except Exception:
                        pass

            return  # success

        except Exception as nim_err:
            print(f"[LLM] NVIDIA NIM error: {nim_err}")
            yield f"[Error: Both Groq and NVIDIA NIM failed. Last error: {nim_err}]"
            return

    # Neither client is available
    yield "[Error: No LLM backend available. Set GROQ_API_KEY and/or NVIDIA_API_KEY.]"


# ── CLI test ──────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    session = "test_session_01"
    print("Kairos LLM Agent — Test Mode (Ctrl+C to exit)")
    print("-" * 50)
    while True:
        try:
            q = input("\nYou: ").strip()
            if not q:
                continue
            print("Kairos: ", end="", flush=True)
            for chunk in generate_streaming_response(session, q):
                print(chunk, end="", flush=True)
            print()
        except KeyboardInterrupt:
            print("\nExiting.")
            break
        except Exception as e:
            print(f"\nError: {e}")
