"""
hybrid_retrieval.py — Hybrid Retrieval Engine (ChromaDB Vector + SQLite Knowledge Graph).

Merges vector similarity search from ChromaDB with 1-2 hop graph traversals across
SQLite entity-relation tables. Deduplicates, scores, and ranks candidates for RAG injection.
"""

import logging
import re
from typing import List, Dict, Tuple, Optional, Any

import memory_store

logger = logging.getLogger("kairos.memory.hybrid_retrieval")


def _extract_query_entities(user_id: str, query: str) -> List[str]:
    """
    Extracts candidate entity names mentioned in the query by matching
    against known entities stored in kg_entities and kg_relations.
    """
    if not query or not query.strip():
        return []

    q_clean = query.strip().lower()
    matched_entities = set()

    # 1. Match known entities from database
    known_entities = memory_store.get_all_entities(user_id)
    for ent in known_entities:
        ename = ent["name"].strip()
        if len(ename) >= 2:
            pattern = r'\b' + re.escape(ename.lower()) + r'\b'
            if re.search(pattern, q_clean):
                matched_entities.add(ename)

    # 2. Extract potential capitalization/noun heuristics if database is fresh
    words = re.findall(r'\b[A-Za-z0-9_-]{3,}\b', query)
    stopwords = {
        "what", "where", "when", "which", "who", "whom", "whose", "why", "how",
        "tell", "show", "give", "list", "about", "project", "working", "with",
        "from", "into", "during", "including", "until", "against", "among",
        "throughout", "despite", "towards", "upon", "concerning", "to", "in",
        "for", "on", "by", "is", "are", "was", "were", "be", "been", "being",
        "have", "has", "had", "do", "does", "did", "can", "could", "should",
        "would", "may", "might", "must", "shall", "the", "a", "an", "and", "or",
    }
    for w in words:
        if w.lower() not in stopwords and len(w) >= 3:
            matched_entities.add(w)

    return list(matched_entities)


def retrieve_hybrid(
    user_id: str,
    query: str,
    top_k: int = 5,
    selected_doc_ids: Optional[List[str]] = None,
) -> Tuple[str, List[Dict[str, Any]]]:
    """
    Hybrid retrieval: Performs ChromaDB vector similarity search + SQLite 1-2 hop graph traversal,
    then applies Cross-Encoder reranking (ms-marco-MiniLM-L-6-v2) to filter top-N down to top-K.

    Returns:
        (context_text_block: str, scored_chunks: List[Dict])
    """
    if not query or not query.strip():
        return ("", [])

    from memory.reranker import rerank, RERANKER_TOP_N

    top_n = max(RERANKER_TOP_N, top_k * 3)

    # ── 1. Vector Search (ChromaDB) ───────────────────────────────────────────
    v_context_str, v_scored_chunks = memory_store.retrieve_vector_context_detailed(
        user_id=user_id,
        query=query,
        top_k=top_n,
        selected_doc_ids=selected_doc_ids,
    )

    # Map candidate fact content / id -> candidate dict
    candidates: Dict[str, Dict[str, Any]] = {}

    for item in v_scored_chunks:
        cid = item.get("id", "")
        preview = item.get("preview", "")
        candidates[cid] = {
            "id": cid,
            "type": item.get("type", "fact"),
            "source": item.get("source", "conversation"),
            "vector_score": float(item.get("score", 0.5)),
            "graph_score": 0.0,
            "final_score": float(item.get("score", 0.5)),
            "content": preview,
            "is_vector": True,
            "is_graph": False,
            "relations": [],
        }

    # ── 2. Graph Traversal Search (SQLite Knowledge Graph) ────────────────────
    query_entities = _extract_query_entities(user_id, query)
    graph_rels = memory_store.get_graph_neighborhood(user_id, query_entities, max_hops=2)

    # Collect facts tied to graph relations
    con = memory_store._conn()
    for rel in graph_rels:
        fact_id = rel.get("source_fact_id")
        hop = rel.get("hop", 1)
        base_g_score = 0.85 if hop == 1 else 0.70

        fact_row = None
        if fact_id:
            fact_row = con.execute(
                "SELECT id, content, source FROM memory_items WHERE id=? AND user_id=?",
                (fact_id, user_id),
            ).fetchone()

        if fact_row:
            fid, content, src = fact_row
            rel_str = f"{rel['source']} --[{rel['relation']}]--> {rel['target']}"
            if fid in candidates:
                # Dual hit (Vector + Graph) -> Apply intersection boost
                cand = candidates[fid]
                cand["is_graph"] = True
                cand["graph_score"] = max(cand["graph_score"], base_g_score)
                cand["final_score"] = min(1.0, round(max(cand["vector_score"], base_g_score) + 0.15, 3))
                cand["relations"].append(rel_str)
            else:
                # Graph-only hit
                candidates[fid] = {
                    "id": fid,
                    "type": "fact",
                    "source": src or "conversation",
                    "vector_score": 0.0,
                    "graph_score": base_g_score,
                    "final_score": round(base_g_score, 3),
                    "content": content,
                    "is_vector": False,
                    "is_graph": True,
                    "relations": [rel_str],
                }

    con.close()

    if not candidates:
        return ("", [])

    # Initial sort before reranker
    initial_candidates = sorted(
        candidates.values(),
        key=lambda c: (c["final_score"], c["is_graph"], c["is_vector"]),
        reverse=True,
    )

    # ── 3. Cross-Encoder Reranking Stage (Top-N -> Top-K) ─────────────────────
    reranked_candidates = rerank(query=query, candidates=initial_candidates, top_k=top_k)

    formatted_results = []
    output_chunks = []

    for item in reranked_candidates:
        cid = item["id"]
        content = item["content"]
        score = item["final_score"]

        if cid == "pinned_fact":
            prefix = "📌 [Pinned Memory]"
        elif item["is_vector"] and item["is_graph"]:
            rel_info = f" ({', '.join(item['relations'][:2])})" if item["relations"] else ""
            prefix = f"• [Vector + Graph Linked{rel_info}]"
        elif item["is_graph"]:
            rel_info = f" ({', '.join(item['relations'][:2])})" if item["relations"] else ""
            prefix = f"• [Graph Linked{rel_info}]"
        else:
            prefix = f"• [From '{item['source']}']" if item["type"] == "document_chunk" else "• [Memory]"

        formatted_results.append(f"{prefix} {content}")
        output_chunks.append({
            "id": cid,
            "type": item["type"],
            "source": item["source"],
            "score": score,
            "preview": content[:120],
            "is_graph_linked": item["is_graph"],
            "relations": item["relations"],
            "rerank_score": item.get("rerank_score"),
        })

    context_str = (
        "## Relevant context from your long-term memory & selected documents:\n"
        + "\n".join(formatted_results)
    )
    return (context_str, output_chunks)

