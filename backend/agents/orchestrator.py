"""
orchestrator.py — High-speed classification & sub-agent router for Kairos architecture.
"""

import json
import logging
import os
import re
import time
from typing import Dict, List, Tuple, Any, Optional, Callable

from agents.base_agent import BaseSubAgent
from agents.coding_agent import CodingAgent
from agents.browsing_agent import BrowsingAgent
from agents.system_agent import SystemAgent
from agents.memory_agent import MemoryAgent
from agents.general_agent import GeneralAgent
from agents.info_agent import InfoAgent
from llm_agent import LOOP_MODEL, GROQ_MODEL
from agent_loop import classify_complexity

logger = logging.getLogger("kairos.agents.orchestrator")

CONFIDENCE_THRESHOLD = float(os.getenv("ORCHESTRATOR_CONFIDENCE_THRESHOLD", "0.70"))

CATEGORIES = [
    "coding",
    "browsing",
    "system_control",
    "research_memory",
    "general_info",
    "chitchat_general",
]

_CLASSIFY_SYSTEM = """\
You are an ultra-fast intent classifier for Kairos AI assistant.
Classify the user's input into EXACTLY ONE category:
1. coding - writing/running code, algorithms, VS Code, Notepad code files, sandbox.
2. browsing - web navigation, visiting websites, Playwright browser tools, YouTube.
3. system_control - opening/closing desktop apps, cursor/keyboard, deleting files, sending WhatsApp/email.
4. research_memory - asking about user facts, past context, ingested PDFs, notes, personal info stored in memory.
5. general_info - asking for current date/time ("aaj date kya hai", "what time is it"), live news ("aaj ki Muzaffarnagar news bata", "tech news today"), live events, weather, sports scores, or real-time web facts.
6. chitchat_general - greetings, casual chat, general conversational Q&A without live search.

Return ONLY valid JSON (no markdown, no prose):
{"category": "<category_name>", "confidence": <0.00_to_1.00>}
"""

_FEW_SHOT_EXAMPLES = [
    ("write a Python fibonacci function", {"category": "coding", "confidence": 0.98}),
    ("open youtube and search lofi music", {"category": "browsing", "confidence": 0.97}),
    ("what did I tell you about my project?", {"category": "research_memory", "confidence": 0.96}),
    ("close calculator and open brave", {"category": "system_control", "confidence": 0.99}),
    ("send a whatsapp message to Vansh", {"category": "system_control", "confidence": 0.96}),
    ("aaj ki date aur time kya hai?", {"category": "general_info", "confidence": 0.98}),
    ("Muzaffarnagar ki news batao", {"category": "general_info", "confidence": 0.97}),
    ("what is the latest news in tech today?", {"category": "general_info", "confidence": 0.96}),
    ("who won the cricket match yesterday?", {"category": "general_info", "confidence": 0.95}),
    ("hey how are you doing today?", {"category": "chitchat_general", "confidence": 0.99}),
]


def classify(
    user_message: str,
    history: Optional[List[Dict]] = None,
    groq_client = None,
    model: str = GROQ_MODEL,
) -> Tuple[str, float]:
    """
    Fast few-shot classification call targeting <150ms latency.
    Returns (category_name, confidence_score).
    """
    t0 = time.time()
    if not groq_client:
        logger.warning("[CLASSIFY] groq_client missing, falling back to chitchat_general")
        return "chitchat_general", 0.50

    messages = [{"role": "system", "content": _CLASSIFY_SYSTEM}]
    for ex_user, ex_out in _FEW_SHOT_EXAMPLES:
        messages.append({"role": "user", "content": ex_user})
        messages.append({"role": "assistant", "content": json.dumps(ex_out)})

    # Append brief recent history context if available (last 2 turns max)
    if history:
        for turn in history[-2:]:
            messages.append(turn)

    messages.append({"role": "user", "content": user_message})

    try:
        resp = groq_client.chat.completions.create(
            model=model,
            messages=messages,
            stream=False,
            max_tokens=35,
            temperature=0.0,
        )
        dt_ms = (time.time() - t0) * 1000
        raw = resp.choices[0].message.content.strip()
        raw_clean = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw, flags=re.DOTALL).strip()
        data = json.loads(raw_clean)

        cat = str(data.get("category", "chitchat_general")).lower().strip()
        conf = float(data.get("confidence", 0.50))

        if cat not in CATEGORIES:
            logger.warning("[CLASSIFY] Invalid category '%s', falling back to chitchat_general", cat)
            cat = "chitchat_general"
            conf = 0.50

        logger.info("[CLASSIFY] result: cat=%s conf=%.2f (latency=%.1fms)", cat, conf, dt_ms)
        return cat, conf

    except Exception as exc:
        dt_ms = (time.time() - t0) * 1000
        logger.warning("[CLASSIFY] classification error (%s) in %.1fms, falling back to chitchat_general", exc, dt_ms)
        return "chitchat_general", 0.50


# Sub-agent instances
_AGENTS = {
    "coding": CodingAgent(),
    "browsing": BrowsingAgent(),
    "system_control": SystemAgent(),
    "research_memory": MemoryAgent(),
    "general_info": InfoAgent(),
    "chitchat_general": GeneralAgent(),
}


def get_agent_for_category(category: str, confidence: float) -> Tuple[BaseSubAgent, str]:
    """
    Selects the sub-agent for the category.
    If confidence < CONFIDENCE_THRESHOLD, defaults to GeneralAgent (chitchat_general).
    """
    if confidence < CONFIDENCE_THRESHOLD:
        logger.info("[ORCHESTRATOR] Low confidence (%.2f < %.2f) → routing to GeneralAgent for clarification",
                    confidence, CONFIDENCE_THRESHOLD)
        return _AGENTS["chitchat_general"], "chitchat_general"
    return _AGENTS.get(category, _AGENTS["chitchat_general"]), category


def orchestrate(
    session_id: str,
    user_message: str,
    history: List[Dict],
    groq_client,
    model: str = GROQ_MODEL,
    emit_event_fn: Optional[Callable[[str, Dict], Any]] = None,
    execute_fn: Optional[Callable[[str, Dict], Dict]] = None,
    user_id: str = "",
    skip_memory: bool = False,
    on_rag_callback = None,
    selected_doc_ids: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """
    Main orchestrator entry point.
    1. Classifies request intent into sub-domain (<150ms target).
    2. Routes to matching sub-agent.
    3. Runs request with full conversation history and sub-agent's restricted toolset.
    """
    if emit_event_fn is None:
        emit_event_fn = lambda event, payload: None

    if execute_fn is None:
        from agent_tools.executor import execute_tool
        execute_fn = execute_tool

    # 1. Classify intent
    category, confidence = classify(user_message, history, groq_client, model=LOOP_MODEL)

    # 2. Select sub-agent (with confidence fallback)
    sub_agent, effective_category = get_agent_for_category(category, confidence)

    # Emit classification neural event for UI/monitoring
    emit_event_fn("ROUTER_CLASSIFIED", {
        "category": category,
        "effectiveCategory": effective_category,
        "confidence": confidence,
        "subAgent": sub_agent.name,
    })

    # 3. Determine complexity (simple vs complex) for loop path decision inside sub-agent
    complexity = classify_complexity(user_message)

    # 4. Execute through sub-agent
    result = sub_agent.run(
        session_id=session_id,
        user_message=user_message,
        history=history,
        groq_client=groq_client,
        model=model,
        emit_event_fn=emit_event_fn,
        execute_fn=execute_fn,
        complexity=complexity,
        user_id=user_id,
        skip_memory=skip_memory,
        on_rag_callback=on_rag_callback,
        selected_doc_ids=selected_doc_ids,
    )

    result["category"] = category
    result["effective_category"] = effective_category
    result["confidence"] = confidence
    result["agent_name"] = sub_agent.name
    return result
