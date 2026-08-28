"""
memory_store.py — ChromaDB-backed long-term memory manager for Kavya.

Collections:
  - user_facts:    salient facts extracted from conversations (per user_id)
  - documents:     chunked ingested PDFs/text files (per user_id)

Embedding model: all-MiniLM-L6-v2 (local, ~90MB, no API key)
"""

import os
import sys
import uuid
import time
import sqlite3
from typing import List, Dict, Optional

try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')
except Exception:
    pass

# ── ChromaDB ──────────────────────────────────────────────────────────────────
try:
    import chromadb
    from chromadb.config import Settings
    from chromadb.utils import embedding_functions

    _CHROMA_DIR = os.path.join(os.path.dirname(__file__), "chroma_db")
    os.makedirs(_CHROMA_DIR, exist_ok=True)

    _chroma_client = chromadb.PersistentClient(path=_CHROMA_DIR)

    # Use local sentence-transformers embedding (downloads ~90MB on first run)
    _ef = embedding_functions.SentenceTransformerEmbeddingFunction(
        model_name="all-MiniLM-L6-v2"
    )

    _facts_collection = _chroma_client.get_or_create_collection(
        name="user_facts",
        embedding_function=_ef,
        metadata={"hnsw:space": "cosine"},
    )
    _docs_collection = _chroma_client.get_or_create_collection(
        name="documents",
        embedding_function=_ef,
        metadata={"hnsw:space": "cosine"},
    )

    CHROMA_AVAILABLE = True
    print("[Memory] ✅ ChromaDB initialized at:", _CHROMA_DIR)

except Exception as _e:
    CHROMA_AVAILABLE = False
    _chroma_client = None
    _facts_collection = None
    _docs_collection = None
    print(f"[Memory] ⚠️  ChromaDB unavailable ({_e}) — long-term memory disabled")


# ── SQLite metadata mirror ────────────────────────────────────────────────────
# Stores display metadata (pinned, timestamps, source) so the UI can list
# memories without doing a ChromaDB full-scan.

_SQLITE_PATH = os.path.join(os.path.dirname(__file__), "memory.db")

def _conn():
    return sqlite3.connect(_SQLITE_PATH)

def _init_tables():
    con = _conn()
    cur = con.cursor()
    cur.executescript("""
        CREATE TABLE IF NOT EXISTS memory_items (
            id          TEXT PRIMARY KEY,
            user_id     TEXT NOT NULL,
            type        TEXT NOT NULL,
            content     TEXT NOT NULL,
            source      TEXT DEFAULT 'conversation',
            pinned      INTEGER DEFAULT 0,
            created_at  REAL NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_memory_user ON memory_items(user_id, type);

        CREATE TABLE IF NOT EXISTS ingested_documents (
            doc_id      TEXT PRIMARY KEY,
            user_id     TEXT NOT NULL,
            doc_name    TEXT NOT NULL,
            chunk_count INTEGER DEFAULT 0,
            created_at  REAL NOT NULL
        );

        CREATE TABLE IF NOT EXISTS kg_entities (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id     TEXT NOT NULL,
            name        TEXT NOT NULL,
            type        TEXT NOT NULL,
            created_at  REAL NOT NULL,
            UNIQUE(user_id, name)
        );
        CREATE INDEX IF NOT EXISTS idx_kg_entities_user_name ON kg_entities(user_id, name);

        CREATE TABLE IF NOT EXISTS kg_relations (
            id             INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id        TEXT NOT NULL,
            source_entity  TEXT NOT NULL,
            relation       TEXT NOT NULL,
            target_entity  TEXT NOT NULL,
            confidence     REAL DEFAULT 1.0,
            source_fact_id TEXT,
            created_at     REAL NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_kg_rel_src ON kg_relations(user_id, source_entity);
        CREATE INDEX IF NOT EXISTS idx_kg_rel_tgt ON kg_relations(user_id, target_entity);
        CREATE INDEX IF NOT EXISTS idx_kg_rel_fact ON kg_relations(user_id, source_fact_id);
    """)
    con.commit()
    con.close()

_init_tables()


# ── Knowledge Graph Helpers ───────────────────────────────────────────────────

def save_graph_elements(
    user_id: str,
    fact_id: str,
    entities: Optional[List[Dict]] = None,
    relations: Optional[List[Dict]] = None,
):
    """Stores extracted entities and relations into SQLite graph tables."""
    now = time.time()
    con = _conn()

    if entities:
        for ent in entities:
            name = str(ent.get("name", "")).strip()
            etype = str(ent.get("type", "concept")).strip().lower()
            if name:
                con.execute(
                    "INSERT OR IGNORE INTO kg_entities (user_id, name, type, created_at) VALUES (?,?,?,?)",
                    (user_id, name, etype, now),
                )

    if relations:
        for rel in relations:
            src = str(rel.get("source", "") or rel.get("source_entity", "")).strip()
            r_type = str(rel.get("relation", "")).strip().lower().replace(" ", "_")
            tgt = str(rel.get("target", "") or rel.get("target_entity", "")).strip()
            conf = float(rel.get("confidence", 1.0))
            if src and r_type and tgt:
                con.execute(
                    "INSERT INTO kg_relations (user_id, source_entity, relation, target_entity, confidence, source_fact_id, created_at) VALUES (?,?,?,?,?,?,?)",
                    (user_id, src, r_type, tgt, conf, fact_id, now),
                )

    con.commit()
    con.close()


def get_relations_for_fact(fact_id: str) -> List[Dict]:
    """Returns all relations created from a specific fact_id."""
    con = _conn()
    rows = con.execute(
        "SELECT id, source_entity, relation, target_entity, confidence FROM kg_relations WHERE source_fact_id=?",
        (fact_id,),
    ).fetchall()
    con.close()
    return [
        {
            "id": r[0],
            "source": r[1],
            "relation": r[2],
            "target": r[3],
            "confidence": r[4],
        }
        for r in rows
    ]


def get_all_entities(user_id: str) -> List[Dict]:
    """Returns all known entities for a user."""
    con = _conn()
    rows = con.execute(
        "SELECT id, name, type, created_at FROM kg_entities WHERE user_id=? ORDER BY name ASC",
        (user_id,),
    ).fetchall()
    con.close()
    return [{"id": r[0], "name": r[1], "type": r[2], "created_at": r[3]} for r in rows]


def get_graph_neighborhood(
    user_id: str, entity_names: List[str], max_hops: int = 2
) -> List[Dict]:
    """
    Performs 1-hop and 2-hop graph traversals from a set of starting entity names.
    Returns relation dicts with 'hop' depth indicator.
    """
    if not entity_names:
        return []

    con = _conn()
    seen_rel_ids = set()
    results = []

    # 1-Hop Traversal
    hop1_entities = set(e.strip().lower() for e in entity_names if e.strip())
    if not hop1_entities:
        con.close()
        return []

    placeholders = ",".join("?" for _ in hop1_entities)
    params = [user_id] + list(hop1_entities) + list(hop1_entities)
    query_1hop = f"""
        SELECT id, source_entity, relation, target_entity, confidence, source_fact_id
        FROM kg_relations
        WHERE user_id = ? AND (LOWER(source_entity) IN ({placeholders}) OR LOWER(target_entity) IN ({placeholders}))
    """
    rows_1hop = con.execute(query_1hop, params).fetchall()

    next_entities = set()
    for r in rows_1hop:
        rid, src, rel, tgt, conf, fid = r
        if rid not in seen_rel_ids:
            seen_rel_ids.add(rid)
            results.append({
                "id": rid,
                "source": src,
                "relation": rel,
                "target": tgt,
                "confidence": conf,
                "source_fact_id": fid,
                "hop": 1,
            })
            next_entities.add(src.lower())
            next_entities.add(tgt.lower())

    # 2-Hop Traversal (if max_hops >= 2)
    if max_hops >= 2 and next_entities:
        p_2hop = ",".join("?" for _ in next_entities)
        params_2hop = [user_id] + list(next_entities) + list(next_entities)
        query_2hop = f"""
            SELECT id, source_entity, relation, target_entity, confidence, source_fact_id
            FROM kg_relations
            WHERE user_id = ? AND (LOWER(source_entity) IN ({p_2hop}) OR LOWER(target_entity) IN ({p_2hop}))
        """
        rows_2hop = con.execute(query_2hop, params_2hop).fetchall()
        for r in rows_2hop:
            rid, src, rel, tgt, conf, fid = r
            if rid not in seen_rel_ids:
                seen_rel_ids.add(rid)
                results.append({
                    "id": rid,
                    "source": src,
                    "relation": rel,
                    "target": tgt,
                    "confidence": conf,
                    "source_fact_id": fid,
                    "hop": 2,
                })

    con.close()
    return results


# ── Public API ─────────────────────────────────────────────────────────────────

def upsert_fact(
    user_id: str,
    text: str,
    source: str = "conversation",
    entities: Optional[List[Dict]] = None,
    relations: Optional[List[Dict]] = None,
) -> str:
    """Store or update a long-term user fact and optional graph elements. Returns fact_id."""
    if not CHROMA_AVAILABLE:
        return ""
    fact_id = f"fact_{user_id}_{uuid.uuid4().hex[:12]}"
    now = time.time()

    _facts_collection.upsert(
        ids=[fact_id],
        documents=[text],
        metadatas=[{"user_id": user_id, "source": source, "created_at": now}],
    )

    con = _conn()
    con.execute(
        "INSERT OR REPLACE INTO memory_items (id, user_id, type, content, source, pinned, created_at) VALUES (?,?,?,?,?,0,?)",
        (fact_id, user_id, "fact", text, source, now),
    )
    con.commit()
    con.close()

    if entities or relations:
        save_graph_elements(user_id, fact_id, entities, relations)

    return fact_id


def upsert_document_chunk(
    user_id: str, doc_id: str, chunk_index: int, text: str, doc_name: str
) -> str:
    """Store one chunk of an ingested document."""
    if not CHROMA_AVAILABLE:
        return ""
    chunk_id = f"{doc_id}_chunk_{chunk_index}"
    now = time.time()

    _docs_collection.upsert(
        ids=[chunk_id],
        documents=[text],
        metadatas=[{
            "user_id": user_id,
            "doc_id": doc_id,
            "doc_name": doc_name,
            "chunk_index": chunk_index,
            "created_at": now,
        }],
    )

    # Mirror chunk content in SQLite for UI listing
    con = _conn()
    con.execute(
        "INSERT OR REPLACE INTO memory_items (id, user_id, type, content, source, pinned, created_at) VALUES (?,?,?,?,?,0,?)",
        (chunk_id, user_id, "document_chunk", text[:300], doc_name, now),
    )
    con.commit()
    con.close()
    return chunk_id


def retrieve_vector_context_detailed(
    user_id: str, query: str, top_k: int = 5, selected_doc_ids: Optional[List[str]] = None
) -> tuple:
    """
    Pure vector similarity search across facts + documents for this user.
    """
    if not CHROMA_AVAILABLE or not query.strip():
        return ("", [])

    results: List[str] = []
    scored_chunks: List[Dict] = []

    # Search facts
    try:
        pinned = _get_pinned_ids(user_id)
        fact_res = _facts_collection.query(
            query_texts=[query],
            n_results=min(top_k, max(1, _facts_collection.count())),
            where={"user_id": user_id},
        )
        docs = fact_res.get("documents", [[]])[0]
        metas = fact_res.get("metadatas", [[]])[0]
        ids = fact_res.get("ids", [[]])[0]
        dists = fact_res.get("distances", [[]])[0] if "distances" in fact_res else [0.2] * len(docs)

        for doc, meta, cid, dist in zip(docs, metas, ids, dists):
            score = max(0.1, min(0.99, round(1.0 - (dist if dist is not None else 0.2), 3)))
            prefix = "📌 " if cid in pinned else "• "
            results.append(f"{prefix}[Memory] {doc}")
            scored_chunks.append({
                "id": cid,
                "type": "fact",
                "source": meta.get("source", "conversation"),
                "score": score,
                "preview": doc[:80],
            })
    except Exception:
        pass

    # Search documents (respecting selected_doc_ids filter)
    should_search_docs = selected_doc_ids is None or len(selected_doc_ids) > 0
    if should_search_docs:
        try:
            if _docs_collection.count() > 0:
                doc_where = {"user_id": user_id}
                if selected_doc_ids is not None and len(selected_doc_ids) == 1:
                    doc_where = {"$and": [{"user_id": user_id}, {"doc_id": selected_doc_ids[0]}]}
                elif selected_doc_ids is not None and len(selected_doc_ids) > 1:
                    doc_where = {"$and": [{"user_id": user_id}, {"doc_id": {"$in": selected_doc_ids}}]}

                doc_res = _docs_collection.query(
                    query_texts=[query],
                    n_results=min(top_k, max(1, _docs_collection.count())),
                    where=doc_where,
                )
                docs = doc_res.get("documents", [[]])[0]
                metas = doc_res.get("metadatas", [[]])[0]
                ids = doc_res.get("ids", [[]])[0]
                dists = doc_res.get("distances", [[]])[0] if "distances" in doc_res else [0.25] * len(docs)

                for doc, meta, cid, dist in zip(docs, metas, ids, dists):
                    if selected_doc_ids is not None and meta.get("doc_id") not in selected_doc_ids:
                        continue
                    src = meta.get("doc_name", "document")
                    score = max(0.1, min(0.99, round(1.0 - (dist if dist is not None else 0.25), 3)))
                    results.append(f"• [From '{src}'] {doc}")
                    scored_chunks.append({
                        "id": cid,
                        "type": "document_chunk",
                        "source": src,
                        "score": score,
                        "preview": doc[:80],
                    })
        except Exception as _doc_err:
            print(f"[RAG] Document query error: {_doc_err}")

    # Also inject pinned facts unconditionally
    try:
        pinned_facts = _get_pinned_facts(user_id)
        for pf in pinned_facts:
            entry = f"📌 [Pinned Memory] {pf}"
            if entry not in results:
                results.insert(0, entry)
                scored_chunks.insert(0, {
                    "id": "pinned_fact",
                    "type": "pinned_fact",
                    "source": "pinned",
                    "score": 1.0,
                    "preview": pf[:80],
                })
    except Exception:
        pass

    if not results:
        return ("", [])

    context_str = "## Relevant context from your long-term memory & selected documents:\n" + "\n".join(results[:top_k + 2])
    return (context_str, scored_chunks[:top_k + 2])


def retrieve_context_detailed(
    user_id: str, query: str, top_k: int = 5, selected_doc_ids: Optional[List[str]] = None
) -> tuple:
    """
    Hybrid retrieval (ChromaDB Vector + SQLite Knowledge Graph).
    """
    from memory.hybrid_retrieval import retrieve_hybrid
    return retrieve_hybrid(user_id=user_id, query=query, top_k=top_k, selected_doc_ids=selected_doc_ids)


def retrieve_context(
    user_id: str, query: str, top_k: int = 5, selected_doc_ids: Optional[List[str]] = None
) -> str:
    """Backward-compatible string wrapper."""
    context_str, _ = retrieve_context_detailed(user_id, query, top_k=top_k, selected_doc_ids=selected_doc_ids)
    return context_str


def list_facts(user_id: str) -> List[Dict]:
    con = _conn()
    rows = con.execute(
        "SELECT id, content, source, pinned, created_at FROM memory_items WHERE user_id=? AND type='fact' ORDER BY pinned DESC, created_at DESC",
        (user_id,)
    ).fetchall()
    con.close()

    result = []
    for r in rows:
        fid = r[0]
        rels = get_relations_for_fact(fid)
        result.append({
            "id": fid,
            "content": r[1],
            "source": r[2],
            "pinned": bool(r[3]),
            "created_at": r[4],
            "relations": rels,
        })
    return result


def list_documents(user_id: str) -> List[Dict]:
    con = _conn()
    rows = con.execute(
        "SELECT doc_id, doc_name, chunk_count, created_at FROM ingested_documents WHERE user_id=? ORDER BY created_at DESC",
        (user_id,)
    ).fetchall()
    con.close()
    return [{"doc_id": r[0], "doc_name": r[1], "chunk_count": r[2], "created_at": r[3]} for r in rows]


def pin_fact(fact_id: str, pinned: bool) -> bool:
    con = _conn()
    con.execute("UPDATE memory_items SET pinned=? WHERE id=?", (1 if pinned else 0, fact_id))
    con.commit()
    con.close()
    return True


def delete_fact(fact_id: str) -> bool:
    try:
        if CHROMA_AVAILABLE:
            _facts_collection.delete(ids=[fact_id])
    except Exception:
        pass
    con = _conn()
    con.execute("DELETE FROM memory_items WHERE id=?", (fact_id,))
    con.execute("DELETE FROM kg_relations WHERE source_fact_id=?", (fact_id,))
    con.commit()
    con.close()
    return True


def delete_document(doc_id: str, user_id: str) -> bool:
    """Delete all chunks for a document from ChromaDB + SQLite."""
    try:
        if CHROMA_AVAILABLE:
            # Get all chunk IDs for this doc
            results = _docs_collection.get(where={"doc_id": doc_id})
            if results["ids"]:
                _docs_collection.delete(ids=results["ids"])
    except Exception:
        pass
    con = _conn()
    con.execute("DELETE FROM memory_items WHERE source=? AND user_id=? AND type='document_chunk'", (doc_id, user_id))
    con.execute("DELETE FROM ingested_documents WHERE doc_id=? AND user_id=?", (doc_id, user_id))
    con.commit()
    con.close()
    return True


def register_document(user_id: str, doc_id: str, doc_name: str, chunk_count: int):
    con = _conn()
    con.execute(
        "INSERT OR REPLACE INTO ingested_documents (doc_id, user_id, doc_name, chunk_count, created_at) VALUES (?,?,?,?,?)",
        (doc_id, user_id, doc_name, chunk_count, time.time()),
    )
    con.commit()
    con.close()


# ── Internal helpers ───────────────────────────────────────────────────────────

def _get_pinned_ids(user_id: str) -> set:
    con = _conn()
    rows = con.execute("SELECT id FROM memory_items WHERE user_id=? AND pinned=1", (user_id,)).fetchall()
    con.close()
    return {r[0] for r in rows}


def _get_pinned_facts(user_id: str) -> List[str]:
    con = _conn()
    rows = con.execute(
        "SELECT content FROM memory_items WHERE user_id=? AND pinned=1 AND type='fact'", (user_id,)
    ).fetchall()
    con.close()
    return [r[0] for r in rows]
