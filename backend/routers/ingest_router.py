from __future__ import annotations
import asyncio
import logging
import tempfile
from pathlib import Path
import shutil
from fastapi import APIRouter, UploadFile, File, HTTPException
from pydantic import BaseModel
from backend.config import MAX_UPLOAD_BYTES, SUPPORTED_EXTS
from backend.ingest import ingest_file, ingest_text
from backend.scraper import scrape

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/ingest", tags=["ingest"])


class URLRequest(BaseModel):
    url: str


def _copy_limited_upload(file: UploadFile, ext: str) -> Path:
    tmp_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as tmp:
            tmp_path = Path(tmp.name)
            remaining = MAX_UPLOAD_BYTES
            while True:
                chunk = file.file.read(1024 * 1024)
                if not chunk:
                    break
                if len(chunk) > remaining:
                    raise HTTPException(413, f"File too large. Maximum upload size is {MAX_UPLOAD_BYTES} bytes.")
                tmp.write(chunk)
                remaining -= len(chunk)
        return tmp_path
    except HTTPException:
        if tmp_path:
            tmp_path.unlink(missing_ok=True)
        raise


@router.post("/file")
async def ingest_file_endpoint(file: UploadFile = File(...)):
    if not file.filename:
        raise HTTPException(400, "No filename provided.")

    ext = Path(file.filename).suffix.lower()
    if ext not in SUPPORTED_EXTS:
        raise HTTPException(
            400,
            f"Unsupported file type '{ext}'. Accepted: {', '.join(sorted(SUPPORTED_EXTS))}",
        )

    tmp_path = _copy_limited_upload(file, ext)
    try:
        result = await asyncio.to_thread(ingest_file, tmp_path, file.filename)
    except Exception as e:
        logger.exception("Ingestion failed for uploaded file %s", file.filename)
        raise HTTPException(422, f"Ingestion failed: {e}") from e
    finally:
        tmp_path.unlink(missing_ok=True)

    return {
        "status": result.status,
        "chunks": result.chunks,
        "latency_ms": int(result.latency * 1000),
        "source": file.filename,
        "detail": result.detail,
    }


@router.post("/pdf")
async def ingest_pdf_endpoint(file: UploadFile = File(...)):
    return await ingest_file_endpoint(file)


@router.post("/url")
async def ingest_url_endpoint(req: URLRequest):
    try:
        text, source = await asyncio.to_thread(scrape, req.url)
        result = await asyncio.to_thread(ingest_text, text, source)
    except ValueError as e:
        raise HTTPException(422, str(e)) from e
    except Exception as e:
        logger.exception("URL ingestion failed for %s", req.url)
        raise HTTPException(422, f"URL ingestion failed: {e}") from e

    return {
        "status": result.status,
        "chunks": result.chunks,
        "latency_ms": int(result.latency * 1000),
        "source": source,
        "detail": result.detail,
    }
