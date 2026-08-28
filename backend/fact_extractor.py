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
You are a personal memory and knowledge graph assistant. Given a single conversation turn, extract:
1. 0-5 SHORT salient facts about the USER (not the assistant).
2. Named entities mentioned (people, projects, tools, places, concepts).
3. Relationships between entities (e.g. "Abhishek -- works_on --> Kairos", "Kairos -- uses --> ChromaDB").

Focus on:
- User identity, preferences, relationships, occupation, location
- Projects, tools, technologies, goals, and problems they mention

Return ONLY a valid JSON object matching this exact schema:
{{
  "facts": ["Abhishek is building Kairos AI assistant"],
  "entities": [
    {{"name": "Abhishek", "type": "person"}},
    {{"name": "Kairos", "type": "project"}}
  ],
  "relations": [
    {{"source": "Abhishek", "relation": "building", "target": "Kairos", "confidence": 0.95}}
  ]
}}

Rules:
- If no salient facts are found, return {{"facts": [], "entities": [], "relations": []}}.
- Do NOT extract facts or entities about the assistant.
- Maximum 5 facts per turn.

Conversation turn:
User: {user_message}
Assistant: {assistant_response}

Return ONLY the JSON object:"""


async def extract_and_store(
    user_id: str,
    user_message: str,
    assistant_response: str,
    session_date: str = "",
):
    """
    Extract salient user facts, entities, and relations from one conversation turn and store them.
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
            model="qwen/qwen3.8-27b",   # Fast model on this key for extraction
            messages=[{"role": "user", "content": prompt}],
            max_tokens=350,
            temperature=0.2,
        )

        raw = response.choices[0].message.content.strip()

        # Parse JSON — handle markdown fences gracefully
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        raw = raw.strip()

        parsed = json.loads(raw)
        if isinstance(parsed, list):
            # Backward compatibility fallback if model returns array of strings
            facts = parsed
            entities = []
            relations = []
        elif isinstance(parsed, dict):
            facts = parsed.get("facts", [])
            entities = parsed.get("entities", [])
            relations = parsed.get("relations", [])
        else:
            return

        source = session_date or "conversation"
        stored = 0
        for fact in facts[:5]:
            if isinstance(fact, str) and fact.strip():
                memory_store.upsert_fact(
                    user_id=user_id,
                    text=fact.strip(),
                    source=source,
                    entities=entities,
                    relations=relations,
                )
                stored += 1

        if stored > 0:
            print(f"[Memory] Extracted {stored} fact(s), {len(entities)} entity(ies), {len(relations)} relation(s) for user {user_id[:8]}...")

    except Exception as e:
        # Silent — never crash the main response loop
        print(f"[Memory] Fact extraction skipped: {e}")

