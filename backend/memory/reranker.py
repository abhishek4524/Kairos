"""
reranker.py — RAG Reranking Stage (Cross-Encoder with LLM Fallback & Graceful Degradation).

Reranks initial top-N candidates (N=15-20) retrieved from ChromaDB + Knowledge Graph
down to final top-K (K=3-5) for LLM prompt context injection.

Primary: cross-encoder/ms-marco-MiniLM-L-6-v2 via sentence-transformers (local, fast CPU/GPU).
Fallback 1: LLM-based relevance scoring prompt via Groq (when RERANKER_MODE=llm or CrossEncoder missing).
Fallback 2: Pass-through top-K (graceful degradation if dependencies or API fail).
"""

import os
import json
import logging
import time
import math
from typing import List, Dict, Any, Optional

logger = logging.getLogger("kairos.memory.reranker")

# Environment configuration
RERANKER_ENABLED = os.getenv("RERANKER_ENABLED", "true").lower() in ("true", "1", "yes")
RERANKER_MODE = os.getenv("RERANKER_MODE", "cross_encoder").lower()  # "cross_encoder", "llm", "disabled"
RERANKER_DEVICE = os.getenv("RERANKER_DEVICE", "cpu").lower()  # "cpu", "cuda"
RERANKER_MODEL_NAME = os.getenv("RERANKER_MODEL_NAME", "cross-encoder/ms-marco-MiniLM-L-6-v2")
RERANKER_TOP_N = int(os.getenv("RERANKER_TOP_N", "15"))
RERANKER_TOP_K = int(os.getenv("RERANKER_TOP_K", "5"))

_cross_encoder_model = None
_cross_encoder_loaded = False


def _get_cross_encoder():
    """Lazily loads CrossEncoder model with graceful error handling."""
    global _cross_encoder_model, _cross_encoder_loaded
    if _cross_encoder_loaded:
        return _cross_encoder_model

    _cross_encoder_loaded = True
    try:
        from sentence_transformers import CrossEncoder
        logger.info("[Reranker] Loading CrossEncoder model '%s' on %s...", RERANKER_MODEL_NAME, RERANKER_DEVICE)
        _cross_encoder_model = CrossEncoder(RERANKER_MODEL_NAME, device=RERANKER_DEVICE)
        logger.info("[Reranker] [OK] CrossEncoder loaded successfully.")
    except Exception as e:
        logger.warning("[Reranker] [WARN] Failed to load CrossEncoder (%s). Falling back to LLM/pass-through mode.", e)
        _cross_encoder_model = None

    return _cross_encoder_model


def _sigmoid(x: float) -> float:
    """Converts unbounded cross-encoder logit into 0.0-1.0 probability score."""
    try:
        return round(1.0 / (1.0 + math.exp(-x)), 3)
    except Exception:
        return 0.5


def _rerank_cross_encoder(query: str, candidates: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Reranks candidates using CrossEncoder."""
    model = _get_cross_encoder()
    if not model:
        raise RuntimeError("CrossEncoder model unavailable")

    pairs = [(query, cand.get("content", "")) for cand in candidates]
    scores = model.predict(pairs)

    reranked = []
    for cand, score in zip(candidates, scores):
        raw_score = float(score)
        norm_score = _sigmoid(raw_score)
        c_copy = dict(cand)
        c_copy["rerank_score"] = norm_score
        # Combine original score with rerank score (70% reranker weight, 30% original weight)
        c_copy["final_score"] = round(0.7 * norm_score + 0.3 * float(cand.get("final_score", 0.5)), 3)
        reranked.append(c_copy)

    return sorted(reranked, key=lambda c: c["final_score"], reverse=True)


def _rerank_llm(query: str, candidates: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """LLM-based reranking fallback using Groq API."""
    from groq import Groq
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        raise RuntimeError("GROQ_API_KEY not configured for LLM reranker")

    client = Groq(api_key=api_key)

    items_prompt = ""
    for idx, cand in enumerate(candidates, 1):
        items_prompt += f"[{idx}] {cand.get('content', '')[:200]}\n"

    prompt = f"""\
You are an expert search reranker. Given a user query and candidate text snippets, score each snippet from 0 to 10 based on relevance.

Query: "{query}"

Candidates:
{items_prompt}

Return ONLY a valid JSON object mapping item index to integer score (0-10):
{{"1": 9, "2": 3, "3": 8}}
"""

    resp = client.chat.completions.create(
        model="qwen/qwen3.8-27b",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=150,
        temperature=0.0,
    )

    raw = resp.choices[0].message.content.strip()
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    raw = raw.strip()

    scores_dict = json.loads(raw)

    reranked = []
    for idx, cand in enumerate(candidates, 1):
        c_copy = dict(cand)
        score_val = float(scores_dict.get(str(idx), 5)) / 10.0
        c_copy["rerank_score"] = score_val
        c_copy["final_score"] = round(0.7 * score_val + 0.3 * float(cand.get("final_score", 0.5)), 3)
        reranked.append(c_copy)

    return sorted(reranked, key=lambda c: c["final_score"], reverse=True)


def rerank(
    query: str,
    candidates: List[Dict[str, Any]],
    top_k: int = RERANKER_TOP_K,
) -> List[Dict[str, Any]]:
    """
    Reranks candidates from initial top-N down to top-K.

    Gracefully falls back across:
      CrossEncoder -> LLM Reranker -> Original Vector/Graph order.
    """
    if not RERANKER_ENABLED or not candidates or RERANKER_MODE == "disabled":
        return candidates[:top_k]

    t0 = time.time()
    reranked_result = None
    method_used = "none"

    if RERANKER_MODE == "cross_encoder":
        try:
            reranked_result = _rerank_cross_encoder(query, candidates)
            method_used = "cross_encoder"
        except Exception as e:
            logger.warning("[Reranker] CrossEncoder prediction failed (%s). Trying LLM fallback.", e)
            try:
                reranked_result = _rerank_llm(query, candidates)
                method_used = "llm_fallback"
            except Exception as e_llm:
                logger.warning("[Reranker] LLM reranking fallback failed (%s). Using pass-through order.", e_llm)
                method_used = "pass_through"

    elif RERANKER_MODE == "llm":
        try:
            reranked_result = _rerank_llm(query, candidates)
            method_used = "llm"
        except Exception as e:
            logger.warning("[Reranker] LLM reranking failed (%s). Using pass-through order.", e)
            method_used = "pass_through"

    if not reranked_result:
        reranked_result = candidates

    dt_ms = (time.time() - t0) * 1000
    logger.info(
        "[Reranker] Reranked %d candidates -> top-%d in %.1fms (method=%s)",
        len(candidates), min(top_k, len(reranked_result)), dt_ms, method_used
    )

    final_k = reranked_result[:top_k]
    for cand in final_k:
        cand["rerank_method"] = method_used
        cand["rerank_latency_ms"] = round(dt_ms, 1)

    return final_k
