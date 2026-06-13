from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from backend.llm import stream_rag

router = APIRouter(prefix="/api", tags=["query"])


@router.get("/stream")
def stream_endpoint(query: str, top_k: int = 5):
    if not query.strip():
        raise HTTPException(400, "Query cannot be empty.")
    return StreamingResponse(
        stream_rag(query, top_k=top_k),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
