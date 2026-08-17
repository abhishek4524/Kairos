"""
fact_extractor.py — Async post-turn salient fact extraction.

After each assistant response, this module fires a small async Groq call
to extract 0-5 user facts and store them in ChromaDB via memory_store.

Runs as asyncio.create_task() — never delays the main response stream.
"""

import os
import json
import asyncio
from groq import AsyncGroq

import memory_store

# Reuse the same API key as llm_agent.py
_groq_async_client = None

def _get_groq_client():
    global _groq_async_client
    if _groq_async_client is None:
        api_key = os.environ.get("GROQ_API_KEY")
        if api_key:
            _groq_async_client = AsyncGroq(api_key=api_key)
    return _groq_async_client

_EXTRACT_PROMPT = """\
You are a personal memory assistant. Given a single conversation turn, extract 0-5 SHORT salient facts about the USER (not the assistant).

Focus on:
- Name, age, location, occupation, relationships
- Preferences (likes/dislikes, hobbies, food, music, topics)
- Goals, important events, recurring topics they mention
- Problems they are solving

Rules:
- Return ONLY a valid JSON array of strings. Example: ["User likes hiking", "User is a software engineer"]
- Return [] if no user-specific facts are found in this turn.
- DO NOT include facts about the assistant.
- Each fact must be a complete, standalone sentence.
- Maximum 5 facts per turn.

Conversation turn:
User: {user_message}
Assistant: {assistant_response}

Return ONLY the JSON array:"""


async def extract_and_store(
    user_id: str,
    user_message: str,
    assistant_response: str,
    session_date: str = "",
):
    """
    Extract salient user facts from one conversation turn and store them.
    Designed to run as asyncio.create_task() — all failures are silently caught.
    """
    if not memory_store.CHROMA_AVAILABLE:
        return

    client = _get_groq_client()
    if not client:
        return

    try:
        prompt = _EXTRACT_PROMPT.format(
            user_message=user_message[:800],
            assistant_response=assistant_response[:800],
        )

        response = await client.chat.completions.create(
            model="llama-3.1-8b-instant",   # small + fast for extraction; preserve 70B quota
            messages=[{"role": "user", "content": prompt}],
            max_tokens=200,
            temperature=0.2,
        )

        raw = response.choices[0].message.content.strip()

        # Parse JSON — handle markdown fences gracefully
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        raw = raw.strip()

        facts: list = json.loads(raw)
        if not isinstance(facts, list):
            return

        source = session_date or "conversation"
        stored = 0
        for fact in facts[:5]:
            if isinstance(fact, str) and fact.strip():
                memory_store.upsert_fact(user_id, fact.strip(), source=source)
                stored += 1

        if stored > 0:
            print(f"[Memory] Extracted {stored} fact(s) for user {user_id[:8]}...")

    except Exception as e:
        # Silent — never crash the main response loop
        print(f"[Memory] Fact extraction skipped: {e}")
