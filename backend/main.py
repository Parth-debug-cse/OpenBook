from __future__ import annotations
import logging
from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from backend.config import API_HOST, API_PORT, CORS_ORIGINS
from backend.watcher import start_watcher, stop_watcher
from backend.embeddings import embed_texts
from backend.llm import _get_llm
from backend.routers.ingest_router import router as ingest_router
from backend.routers.query_router import router as query_router
from backend.routers.tts_router import router as tts_router
from backend.routers.docs_router import router as docs_router

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting OpenBook …")
    start_watcher()

    logger.info("Pre-warming embedding model …")
    embed_texts(["warmup"])

    logger.info("Pre-warming LLM …")
    try:
        _get_llm()
    except Exception as e:
        logger.warning("LLM warmup failed (will load on first query): %s", e)

    logger.info("OpenBook ready.")
    yield

    stop_watcher()
    logger.info("OpenBook stopped.")


app = FastAPI(title="OpenBook API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health")
def health():
    return {"status": "ok"}

app.include_router(ingest_router)
app.include_router(query_router)
app.include_router(tts_router)
app.include_router(docs_router)

_frontend_dist = Path(__file__).parent.parent / "frontend" / "dist"
if _frontend_dist.exists():
    app.mount("/", StaticFiles(directory=str(_frontend_dist), html=True), name="frontend")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.main:app", host=API_HOST, port=API_PORT, reload=False, workers=1)
