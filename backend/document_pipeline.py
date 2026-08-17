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


# ── Text extraction ────────────────────────────────────────────────────────────

def _extract_text_from_pdf(file_path: str) -> str:
    try:
        from pypdf import PdfReader
        reader = PdfReader(file_path)
        pages = []
        for page in reader.pages:
            text = page.extract_text()
            if text:
                pages.append(text)
        return "\n\n".join(pages)
    except Exception as e:
        raise RuntimeError(f"PDF extraction failed: {e}")


def _extract_text_from_txt(file_path: str) -> str:
    with open(file_path, "r", encoding="utf-8", errors="replace") as f:
        return f.read()


def extract_text(file_path: str) -> str:
    ext = os.path.splitext(file_path)[1].lower()
    if ext == ".pdf":
        return _extract_text_from_pdf(file_path)
    elif ext in (".txt", ".md"):
        return _extract_text_from_txt(file_path)
    else:
        raise ValueError(f"Unsupported file type: {ext}. Use .pdf, .txt, or .md")


# ── Main ingestion entry point ────────────────────────────────────────────────

def ingest_file(user_id: str, file_path: str, doc_name: str = "") -> dict:
    """
    Extract, chunk, embed and store a document in ChromaDB.
    Returns summary: {doc_id, doc_name, chunk_count, status}
    """
    if not memory_store.CHROMA_AVAILABLE:
        return {"status": "error", "message": "ChromaDB is not available"}

    if not doc_name:
        doc_name = os.path.basename(file_path)

    # 1. Extract raw text
    try:
        raw_text = extract_text(file_path)
    except Exception as e:
        return {"status": "error", "message": str(e)}

    if not raw_text.strip():
        return {"status": "error", "message": "File appears to be empty or unreadable"}

    # 2. Chunk
    chunks = _chunk_text(raw_text, chunk_size=800, overlap=200)
    if not chunks:
        return {"status": "error", "message": "No text content found in document"}

    # 3. Embed + store each chunk
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

    print(f"[DocPipeline] ✅ Ingested '{doc_name}' → {stored}/{len(chunks)} chunks (doc_id={doc_id})")

    return {
        "status": "success",
        "doc_id": doc_id,
        "doc_name": doc_name,
        "chunk_count": stored,
        "total_chars": len(raw_text),
    }
