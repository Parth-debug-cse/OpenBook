from __future__ import annotations
import asyncio
from fastapi import APIRouter, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel
from backend.config import TTS_MAX_CHARS
from backend.tts import synthesise

router = APIRouter(prefix="/api/tts", tags=["tts"])


class TTSRequest(BaseModel):
    text: str
    voice: str = "af_sarah"
    speed: float = 1.0


@router.post("")
async def tts_endpoint(req: TTSRequest):
    if len(req.text) > TTS_MAX_CHARS:
        raise HTTPException(400, f"Text too long. Max {TTS_MAX_CHARS} characters.")
    try:
        wav_bytes = await asyncio.to_thread(synthesise, req.text, req.voice, req.speed)
    except (RuntimeError, FileNotFoundError) as e:
        raise HTTPException(503, f"TTS unavailable: {e}") from e
    return Response(content=wav_bytes, media_type="audio/wav")
