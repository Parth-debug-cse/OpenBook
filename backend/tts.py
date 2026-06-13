from __future__ import annotations
import hashlib
import logging
import time
from pathlib import Path
from functools import lru_cache
import numpy as np
import soundfile as sf
from backend.config import TTS_MODEL_PATH, TTS_VOICES_PATH, TTS_CACHE_DIR, TTS_VOICE, TTS_SPEED, TTS_SAMPLE_RATE, TTS_CACHE_MAX_FILES, TTS_CACHE_MAX_BYTES, TTS_CACHE_TTL_SECONDS

logger = logging.getLogger(__name__)

try:
    from kokoro_onnx import Kokoro as _KokoroLib
    _HAS_KOKORO = True
except ImportError:
    _HAS_KOKORO = False
    logger.warning("kokoro-onnx not installed. TTS disabled.")

_kokoro = None


def _get_kokoro():
    global _kokoro
    if not _HAS_KOKORO:
        raise RuntimeError("kokoro-onnx not available. Install it: pip install kokoro-onnx")
    if _kokoro is None:
        if not TTS_MODEL_PATH.exists():
            raise FileNotFoundError(
                f"TTS model not found: {TTS_MODEL_PATH}. "
                "Download kokoro-v0_19.onnx and voices.bin into models/."
            )
        _kokoro = _KokoroLib(str(TTS_MODEL_PATH), str(TTS_VOICES_PATH))
    return _kokoro


def _cache_path(text: str, voice: str, speed: float) -> Path:
    key = hashlib.md5(f"{text}|{voice}|{speed}".encode()).hexdigest()
    return TTS_CACHE_DIR / f"{key}.wav"


def _cleanup_old_cache() -> None:
    """Remove expired or excess cache files."""
    now = time.time()
    cache_files = list(TTS_CACHE_DIR.glob("*.wav"))
    
    # Remove TTL-expired files
    for cache_file in cache_files:
        age = now - cache_file.stat().st_mtime
        if age > TTS_CACHE_TTL_SECONDS:
            try:
                cache_file.unlink()
                logger.debug("Removed expired TTS cache: %s", cache_file.name)
            except OSError:
                pass
    
    # Re-list after cleanup
    cache_files = list(TTS_CACHE_DIR.glob("*.wav"))
    
    # Enforce file count limit
    if len(cache_files) > TTS_CACHE_MAX_FILES:
        cache_files.sort(key=lambda f: f.stat().st_mtime)
        excess = cache_files[:len(cache_files) - TTS_CACHE_MAX_FILES]
        for cache_file in excess:
            try:
                cache_file.unlink()
                logger.debug("Removed excess TTS cache: %s", cache_file.name)
            except OSError:
                pass
        cache_files = cache_files[len(excess):]
    
    # Enforce byte limit
    total_bytes = sum(f.stat().st_size for f in cache_files)
    if total_bytes > TTS_CACHE_MAX_BYTES:
        cache_files.sort(key=lambda f: f.stat().st_mtime)
        for cache_file in cache_files:
            if total_bytes <= TTS_CACHE_MAX_BYTES:
                break
            try:
                total_bytes -= cache_file.stat().st_size
                cache_file.unlink()
                logger.debug("Removed TTS cache to free space: %s", cache_file.name)
            except OSError:
                pass


def synthesise(text: str, voice: str = TTS_VOICE, speed: float = TTS_SPEED) -> bytes:
    cache_file = _cache_path(text, voice, speed)
    if cache_file.exists():
        return cache_file.read_bytes()

    # Cleanup cache before generating new audio
    _cleanup_old_cache()

    kokoro  = _get_kokoro()
    samples, sr = kokoro.create(text, voice=voice, speed=speed, lang="en-us")

    sf.write(str(cache_file), samples, sr, format="WAV", subtype="PCM_16")
    return cache_file.read_bytes()
