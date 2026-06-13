from __future__ import annotations
import hashlib
import time
from dataclasses import dataclass
from pathlib import Path
from typing import List
import fitz
from langchain_text_splitters import RecursiveCharacterTextSplitter
from backend.config import CHUNK_SIZE, CHUNK_OVERLAP, SUPPORTED_EXTS
from backend.embeddings import embed_texts
from backend.vectordb import add_chunks, delete_doc, doc_exists


@dataclass
class IngestResult:
    chunks: int
    latency: float
    status: str = "ok"
    detail: str = ""


def _doc_id(source: str) -> str:
    return hashlib.md5(source.encode()).hexdigest()


def _split(text: str) -> List[str]:
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
        separators=["\n\n", "\n", ". ", " ", ""],
    )
    return splitter.split_text(text)


def _store_chunks(source: str, page_chunks: List[dict], replace: bool = False) -> IngestResult:
    t0 = time.time()
    doc_id = _doc_id(source)

    if doc_exists(doc_id):
        if replace:
            delete_doc(doc_id)
        else:
            return IngestResult(
                0, time.time() - t0,
                status="duplicate",
                detail=f"Already ingested as '{source}'. Delete it first to re-ingest.",
            )

    if not page_chunks:
        return IngestResult(
            0, time.time() - t0,
            status="empty",
            detail="No extractable text found in this file.",
        )

    texts = [c["text"] for c in page_chunks]
    vectors = embed_texts(texts)

    for c, v in zip(page_chunks, vectors):
        c["vector"] = v

    add_chunks(page_chunks)
    return IngestResult(len(page_chunks), time.time() - t0)


def _extract_pdf_page_text(page) -> str:
    """Extract text from PDF page preserving layout structure."""
    # Try to extract with layout awareness for better readability
    try:
        # Get text with layout/structure info
        text_dict = page.get_text("dict")
        blocks = []
        
        for block in text_dict.get("blocks", []):
            if block["type"] == 0:  # Text block
                block_text = []
                for line in block.get("lines", []):
                    line_text = []
                    for span in line.get("spans", []):
                        if span.get("text", "").strip():
                            line_text.append(span["text"])
                    if line_text:
                        block_text.append(" ".join(line_text))
                
                if block_text:
                    text = "\n".join(block_text)
                    if text.strip():
                        blocks.append(text.strip())
        
        return "\n\n".join(blocks) if blocks else ""
    except Exception:
        # Fallback to simple text extraction if layout parsing fails
        pass
    
    # Fallback: extract raw text with position-based ordering
    blocks = []
    for x0, y0, x1, y1, text, _block_no, block_type in page.get_text("blocks"):
        if block_type == 0 and text.strip():
            blocks.append((y0, x0, text.strip()))
    
    blocks.sort()
    return "\n\n".join(text for _y, _x, text in blocks)


def ingest_pdf(path: Path, source: str | None = None, replace: bool = False) -> IngestResult:
    source = source or path.name
    doc_id = _doc_id(source)

    if doc_exists(doc_id):
        if replace:
            delete_doc(doc_id)
        else:
            return IngestResult(
                0, 0,
                status="duplicate",
                detail=f"Already ingested as '{source}'. Delete it first to re-ingest.",
            )

    doc = fitz.open(str(path))
    all_chunks = []

    try:
        for page_num, page in enumerate(doc):
            page_text = _extract_pdf_page_text(page)
            if not page_text.strip():
                continue
            chunks = _split(page_text)
            for idx, chunk_text in enumerate(chunks):
                all_chunks.append({
                    "doc_id": doc_id,
                    "source": source,
                    "page": page_num,
                    "chunk_idx": idx,
                    "text": chunk_text,
                })
    finally:
        doc.close()

    return _store_chunks(source, all_chunks, replace=replace)


def ingest_text_file(path: Path, source: str | None = None, replace: bool = False) -> IngestResult:
    source = source or path.name
    doc_id = _doc_id(source)

    if doc_exists(doc_id):
        if replace:
            delete_doc(doc_id)
        else:
            return IngestResult(
                0, 0,
                status="duplicate",
                detail=f"Already ingested as '{source}'. Delete it first to re-ingest.",
            )

    text = path.read_text(encoding="utf-8", errors="replace")
    chunks = _split(text)
    records = [
        {
            "doc_id": doc_id,
            "source": source,
            "page": 0,
            "chunk_idx": idx,
            "text": chunk_text,
        }
        for idx, chunk_text in enumerate(chunks)
    ]
    return _store_chunks(source, records, replace=replace)


def ingest_text(text: str, source: str, page: int = 0, replace: bool = False) -> IngestResult:
    doc_id = _doc_id(source)

    if doc_exists(doc_id):
        if replace:
            delete_doc(doc_id)
        else:
            return IngestResult(
                0, 0,
                status="duplicate",
                detail=f"Already ingested as '{source}'. Delete it first to re-ingest.",
            )

    chunks = _split(text)
    records = [
        {
            "doc_id": doc_id,
            "source": source,
            "page": page,
            "chunk_idx": idx,
            "text": chunk_text,
        }
        for idx, chunk_text in enumerate(chunks)
    ]
    return _store_chunks(source, records, replace=replace)


def ingest_file(path: Path, source: str | None = None, replace: bool = False) -> IngestResult:
    ext = path.suffix.lower()
    if ext not in SUPPORTED_EXTS:
        return IngestResult(
            0, 0,
            status="unsupported",
            detail=f"Unsupported file type '{ext}'. Use: {', '.join(sorted(SUPPORTED_EXTS))}",
        )

    source = source or path.name
    if ext == ".pdf":
        return ingest_pdf(path, source=source, replace=replace)
    return ingest_text_file(path, source=source, replace=replace)
