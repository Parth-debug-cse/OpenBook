import os
import platform
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

ROOT = Path(__file__).resolve().parent.parent
MODELS_DIR = ROOT / "models"
DATA_DIR = ROOT / "data"
NOTES_DIR = ROOT / "notes"
LANCEDB_DIR = DATA_DIR / "lancedb"
TTS_CACHE_DIR = DATA_DIR / "tts_cache"

for _d in [MODELS_DIR, NOTES_DIR, LANCEDB_DIR, TTS_CACHE_DIR]:
    _d.mkdir(parents=True, exist_ok=True)


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except ValueError:
        return default


def _env_float(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, str(default)))
    except ValueError:
        return default


def _env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _parse_env_list(name: str, default: list[str]) -> list[str]:
    value = os.getenv(name)
    if not value:
        return default
    return [item.strip() for item in value.split(",") if item.strip()]


def find_model(*patterns: str) -> Path:
    for pattern in patterns:
        path = MODELS_DIR / pattern
        if "*" in pattern:
            matches = sorted(MODELS_DIR.glob(pattern))
            if matches:
                return matches[0]
        elif path.exists():
            return path
    return MODELS_DIR / patterns[0]


LLM_MODEL_PATH = find_model(
    "LFM2-1.2B-RAG-Q4_K_M.gguf",
    "lfm-1.2b-q4_k_m.gguf",
    "lfm-1.2b*.gguf",
    "*.gguf",
)
TTS_MODEL_PATH = MODELS_DIR / "kokoro-v0_19.onnx"
TTS_VOICES_PATH = MODELS_DIR / "voices.bin"

LLM_N_CTX = _env_int("LLM_N_CTX", 2048)
LLM_N_THREADS = _env_int("LLM_N_THREADS", 4)
LLM_N_BATCH = _env_int("LLM_N_BATCH", 512)
LLM_N_GPU_LAYERS = _env_int(
    "LLM_N_GPU_LAYERS",
    16 if platform.system() == "Darwin" and platform.machine() == "arm64" else 0,
)
LLM_MAX_TOKENS = _env_int("LLM_MAX_TOKENS", 512)
LLM_TEMPERATURE = _env_float("LLM_TEMPERATURE", 0.1)
LLM_REPEAT_PENALTY = _env_float("LLM_REPEAT_PENALTY", 1.1)
LLM_TOP_K = _env_int("LLM_TOP_K", 40)
LLM_TOP_P = _env_float("LLM_TOP_P", 0.95)

CHUNK_SIZE = _env_int("CHUNK_SIZE", 400)
CHUNK_OVERLAP = _env_int("CHUNK_OVERLAP", 60)
TOP_K_RETRIEVAL = _env_int("TOP_K_RETRIEVAL", 5)
EMBED_MODEL = os.getenv("EMBED_MODEL", "nomic-ai/nomic-embed-text-v1.5-Q")
EMBED_DIM = _env_int("EMBED_DIM", 768)
SUPPORTED_EXTS = {".pdf", ".txt", ".md"}
LANCEDB_TABLE = os.getenv("LANCEDB_TABLE", "openbook_chunks")
LANCEDB_RESET_ON_DIM_CHANGE = _env_bool("LANCEDB_RESET_ON_DIM_CHANGE", True)

TTS_VOICE = os.getenv("TTS_VOICE", "af_sarah")
TTS_SPEED = _env_float("TTS_SPEED", 1.0)
TTS_SAMPLE_RATE = _env_int("TTS_SAMPLE_RATE", 24000)
TTS_MAX_CHARS = _env_int("TTS_MAX_CHARS", 2000)
TTS_CACHE_MAX_FILES = _env_int("TTS_CACHE_MAX_FILES", 200)
TTS_CACHE_MAX_BYTES = _env_int("TTS_CACHE_MAX_BYTES", 200 * 1024 * 1024)
TTS_CACHE_TTL_SECONDS = _env_int("TTS_CACHE_TTL_SECONDS", 7 * 24 * 60 * 60)

API_HOST = os.getenv("API_HOST", "127.0.0.1")
API_PORT = _env_int("API_PORT", 8000)
OPENBOOK_API_KEY = os.getenv("OPENBOOK_API_KEY") or os.getenv("API_KEY")
CORS_ALLOW_ALL = _env_bool("CORS_ALLOW_ALL", False)
CORS_ORIGINS = _parse_env_list("CORS_ORIGINS", ["http://localhost:5173", "http://127.0.0.1:5173"])

MAX_UPLOAD_BYTES = _env_int("MAX_UPLOAD_BYTES", 50 * 1024 * 1024)
