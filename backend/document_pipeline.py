"""
document_pipeline.py — PDF/text document ingestion into ChromaDB.

Supports: .pdf, .txt, .md
Strategy: 800-char chunks with 200-char overlap.
"""

import os
import sys
import uuid
import time
from typing import List

try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')
except Exception:
    pass

import memory_store


# ── Chunking ──────────────────────────────────────────────────────────────────

def _chunk_text(text: str, chunk_size: int = 800, overlap: int = 200) -> List[str]:
    """Split text into overlapping chunks."""
    chunks = []
    start = 0
    text = text.strip()
    while start < len(text):
        end = min(start + chunk_size, len(text))
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        if end >= len(text):
            break
        start += chunk_size - overlap
    return chunks


from documents.ingestion import ingest_file as parse_document, ParsedDocument


# ── Text extraction ────────────────────────────────────────────────────────────

def extract_text(file_path: str) -> str:
    parsed = parse_document(file_path)
    if not parsed.success and not parsed.extracted_text:
        raise ValueError(parsed.error_message or f"Unsupported or unreadable file: {file_path}")
    return parsed.extracted_text


# ── Main ingestion entry point ────────────────────────────────────────────────

def ingest_file(user_id: str, file_path: str, doc_name: str = "") -> dict:
    """
    Extract, chunk, embed and store a document in ChromaDB.
    Supports: .pdf, .docx, .csv, .xlsx, .jpg, .jpeg, .png, .txt, .md
    Returns summary: {doc_id, doc_name, file_type, chunk_count, warnings, status}
    """
    if not memory_store.CHROMA_AVAILABLE:
        return {"status": "error", "message": "ChromaDB is not available"}

    if not doc_name:
        doc_name = os.path.basename(file_path)

    # 1. Parse document using unified ingestion engine
    parsed = parse_document(file_path)
    if not parsed.success and not parsed.extracted_text:
        return {"status": "error", "message": parsed.error_message or "File parsing failed"}

    raw_text = parsed.extracted_text
    if not raw_text.strip():
        return {
            "status": "error",
            "message": parsed.error_message or "File appears to be empty or unreadable",
            "warnings": parsed.warnings,
        }

    # 2. Chunk text for vector embedding
    chunks = _chunk_text(raw_text, chunk_size=800, overlap=200)
    if not chunks:
        return {"status": "error", "message": "No text content found in document", "warnings": parsed.warnings}

    # 3. Embed + store each chunk in ChromaDB
    doc_id = f"doc_{user_id[:8]}_{uuid.uuid4().hex[:12]}"
    stored = 0

    for i, chunk in enumerate(chunks):
        try:
            memory_store.upsert_document_chunk(
                user_id=user_id,
                doc_id=doc_id,
                chunk_index=i,
                text=chunk,
                doc_name=doc_name,
            )
            stored += 1
        except Exception as e:
            print(f"[DocPipeline] Chunk {i} failed: {e}")
            continue

    # 4. Register in SQLite metadata
    memory_store.register_document(user_id, doc_id, doc_name, stored)

    print(f"[DocPipeline] ✅ Ingested '{doc_name}' ({parsed.file_type}) → {stored}/{len(chunks)} chunks (doc_id={doc_id})")

    return {
        "status": "success",
        "doc_id": doc_id,
        "doc_name": doc_name,
        "file_type": parsed.file_type,
        "chunk_count": stored,
        "total_chars": len(raw_text),
        "warnings": parsed.warnings,
    }

