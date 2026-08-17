import os
import json
import asyncio
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
    print(f"[Redis] ⚠️  Connection failed ({_redis_err}) — running WITHOUT Redis cache (chat will still work via MongoDB)")
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


# ── Per-character system prompts ──────────────────────────────────────────────
_EMOTION_GESTURE_BLOCK = """
## CRITICAL RULE — EMOTION & GESTURE TAG:
1. The VERY FIRST word of your response MUST be exactly ONE gesture/emotion tag from this list:
[greeting] [activeListening] [confidentSpeech] [leadership] [disagreement] [opposition]
[comforting] [surprise] [casualChat] [relaxed] [annoyed] [negotiation] [presentation]
[explaining] [thoughtfulness] [approval] [anger] [displeasure] [openness] [farewell]
[eyeContact] [interestedFlash] [receptive] [engaged] [attentive] [blushing] [coySmile]
[preening] [fidgeting] [focused] [synchrony] [jollyLaughter] [friendlyContact]
[gazeShift] [sharedFocus] [openPosture]

2. NEVER output any emotion or gesture tag anywhere else in your message (no mid-sentence or trailing tags like [helpful], [simple], [confident]).
3. NEVER say or spell out emotion words in your spoken response. The tag is purely a metadata instruction for your 3D avatar and voice modulation.

Format example — User: "Can you write Python code to add 2 and 2?"
Response: [explaining] Here is the Python code:
```python
result = 2 + 2
print(result)
```
"""

_SHARED_RULES = """
## RESPONSE LENGTH & STYLE (CRITICAL):
- **Match your answer length exactly to what is requested.**
- Simple actions/requests (e.g. open/close app, search youtube, play music) → 1 brief sentence only. ("Done, opening YouTube for you!" or "Done, closing Calculator.")
- Code requests → Provide the clean code block directly with 1 sentence explanation at most. Do not write multiple paragraphs of tutorials unless the user asks for an in-depth explanation.
- Factual questions → 1-2 sentences directly answering the question.
- **NEVER begin with filler words like "Sure!", "Of course!", "Certainly!", "Great question!" or repetitive pleasantries.**
- **NEVER over-explain what you just did.**

## CREATOR CONTEXT:
This app was created by Abhishek Kumar (a Full-Stack Engineer).
DO NOT mention this unless the user specifically asks "who made you" or "who is your creator". Never offer this information proactively. Do not assume the user is Abhishek Kumar unless they tell you.

## USER IDENTITY:
In a new session, you don't know who the user is. If they ask 'who am I', honestly reply that "I don't know your name yet, could you tell me?"

## AI DISCLOSURE:
If asked directly if you are an AI, honestly say 'yes'. Do not repeatedly mention it unless asked.
"""
SYSTEM_PROMPT = """
Your name is **Kavya**. You are a friendly, warm, yet professional and capable personal assistant.

## PERSONALITY & SPEAKING STYLE:
- Tone: Warm, helpful, clear, and professional. 
- You are not robotic or overly formal like a traditional butler AI, but you are highly capable and intelligent.
- Respond like a smart, empathetic colleague or friend who is always ready to assist.
- Never lecture, never judge. Always be supportive.

## LANGUAGE & COMPREHENSION POLICY (CRITICAL):
- The user may speak or type in Hindi, English, or Hinglish (mixed).
- Understand their intent regardless of the language they use.
- **ALWAYS respond in clear, natural English ONLY.** 
- **NEVER respond in Hindi or Hinglish, even if the user speaks or writes in Hindi.**
- Your spoken voice and text output must remain 100% English.

## INTRO:
"Hi! I'm Kavya, your personal assistant. How can I help you today?"
{emotion_block}{shared}
"""


from agent_tools.registry import format_system_tools_prompt

def get_system_prompt(language: str = "en") -> str:
    prompt = SYSTEM_PROMPT.format(
        emotion_block=_EMOTION_GESTURE_BLOCK,
        shared=_SHARED_RULES,
    )
    # Inject desktop agentic tools instructions
    prompt += "\n\n" + format_system_tools_prompt()
    return prompt.strip()

# ── Models ────────────────────────────────────────────────────────────────────
GROQ_MODEL = "groq/compound"              # Best available on this Groq account (fast reasoning)
NVIDIA_MODEL = "meta/llama-3.1-8b-instruct"  # NVIDIA NIM hosted Llama

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
    # Fallback: load from MongoDB / SQLite
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
            rag_context = memory_store.retrieve_context(user_id, user_message, top_k=5)
        except Exception as _rag_err:
            print(f"[RAG] Context retrieval failed: {_rag_err}")

    # ── Build system prompt (with optional RAG block injected) ────────────────
    system_content = get_system_prompt(language)
    if rag_context:
        system_content += f"\n\n{rag_context}"

    # Inject a reinforcement reminder just before the user's message to override
    # any Hindi/Hinglish patterns learned from old conversation history.
    _english_reminder = {
        "role": "system",
        "content": "REMINDER: Regardless of the language in the conversation history or the user's message, your response MUST be in English only. Never respond in Hindi, Hinglish, or any other language."
    }
    messages = [{"role": "system", "content": system_content}] + history[:-1] + [_english_reminder] + [history[-1]]

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
                db.save_turn(session_id, avatar_file, "assistant", clean_response)
                history.append({"role": "assistant", "content": clean_response})
                history = summarize_history_if_needed(session_id, avatar_file, history)
                save_chat_history(session_id, avatar_file, history)

                # ── Async fact extraction (non-blocking) ─────────────────────
                if user_id:
                    try:
                        loop = asyncio.get_event_loop()
                        if loop.is_running():
                            asyncio.create_task(
                                fact_extractor.extract_and_store(user_id, user_message, clean_response)
                            )
                        else:
                            loop.run_until_complete(
                                fact_extractor.extract_and_store(user_id, user_message, clean_response)
                            )
                    except Exception as _fe:
                        print(f"[Memory] Fact extraction task failed to start: {_fe}")

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
                messages=messages,
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
                db.save_turn(session_id, avatar_file, "assistant", clean_response)
                history.append({"role": "assistant", "content": clean_response})
                history = summarize_history_if_needed(session_id, avatar_file, history)
                save_chat_history(session_id, avatar_file, history)

                # ── Async fact extraction (non-blocking) ─────────────────────
                if user_id:
                    try:
                        loop = asyncio.get_event_loop()
                        if loop.is_running():
                            asyncio.create_task(
                                fact_extractor.extract_and_store(user_id, user_message, clean_response)
                            )
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
    print("Kavya LLM Agent — Test Mode (Ctrl+C to exit)")
    print("---------------------------------------------")
    while True:
        try:
            msg = input("\nYou: ")
            if not msg.strip():
                continue
            print("Kavya: ", end="", flush=True)
            for chunk in generate_streaming_response(session, msg):
                print(chunk, end="", flush=True)
            print()
        except KeyboardInterrupt:
            print("\nExiting.")
            break
        except Exception as e:
            print(f"\nError: {e}")
