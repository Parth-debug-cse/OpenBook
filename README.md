# OpenBook — Offline RAG Study Assistant

A fully offline, cross-platform RAG study assistant. No cloud, no Ollama, no Docker.

## Quick Start

```bash
# First time: downloads models and sets up environment
bash start.sh
```

Then either:
- **Drag & drop** PDF/TXT/MD files into the sidebar in the UI, or
- **Copy files** into the `notes/` folder at the project root (watched automatically), or
- **Paste a URL** or YouTube link in the URL input field

Ask questions in the chat — OpenBook retrieves relevant chunks and answers from your notes.

## Model Downloads

### LLM — Liquid AI LFM-1.2B (Q4_K_M GGUF)

**Required for inference.**

Download from HuggingFace:
```
https://huggingface.co/bartowski/lfm-1.2b-GGUF
```

File to download: `LFM2-1.2B-RAG-Q4_K_M.gguf` (≈860 MB)

Place in: `models/` directory

**Alternative:** Use any LFM-1.2B GGUF file; OpenBook auto-detects via wildcard patterns in `config.py`.

### TTS — Kokoro-82M ONNX

**Optional.** Leave out to disable TTS; the app works without it.

Download from HuggingFace:
```
https://huggingface.co/thewh1teagle/kokoro-onnx
```

Files to download:
- `kokoro-v0_19.onnx` (≈100 MB)
- `voices.bin` (≈20 MB)

Place both in: `models/` directory

## System Requirements

- **CPU**: 4-core Intel i3 / Apple Silicon (M1+)
- **RAM**: 8 GB (can work with 6 GB for smaller models)
- **Storage**: 2 GB free (for models + cache)
- **GPU**: Not required (optional: Metal support on Apple Silicon if compiled)

## Installation & Setup

### 1. Prerequisites

- Python 3.10+
- Node.js 18+ (for frontend build)
- bash or PowerShell

### 2. Clone or download the project

```bash
cd /path/to/OpenBook
```

### 3. Run setup (one-time)

```bash
bash setup.sh              # macOS/Linux
bash setup_windows.ps1    # Windows PowerShell
```

This:
- Creates a Python venv
- Installs dependencies
- Compiles llama-cpp-python with CPU optimizations (AVX2/Metal)
- Builds the React frontend

### 4. Download models into `models/`

See [Model Downloads](#model-downloads) above.

### 5. Start the app

```bash
bash start.sh
```

- Opens `http://localhost:8000` in your default browser
- Logs to stdout and `data/openbook.log`

**Note:** First startup pre-warms the embedding and LLM models (~30s).

## Features

### Document Ingestion

- **File types**: PDF, TXT, Markdown
- **Max file size**: 50 MB (configurable)
- **Deduplication**: By filename/URL hash; update files to re-ingest
- **Auto-watcher**: Copies to `notes/` folder are ingested automatically

### Retrieval-Augmented Generation (RAG)

- **Retrieval**: Top-5 most similar chunks (configurable)
- **Context window**: 2048 tokens (auto-truncates if needed)
- **Scoring**: Cosine similarity via LanceDB vector search
- **Fallback**: Explicit message if no documents or no answer in context

### Web & Video Ingestion

- **URLs**: Paste any web link; OpenBook extracts text using Trafilatura
- **YouTube**: Paste a YouTube link; fetches transcript
- **Blocking**: Private IPs, loopback, cloud metadata endpoints blocked for security

### Text-to-Speech

- **Voice**: Kokoro-82M ONNX (optional)
- **Caching**: LRU cache with eviction; TTL + size limits
- **Speed**: Configurable (0.5x – 2.0x)

### UI

- **Desktop**: 3-column layout (sidebar | chat | sources)
- **Tablet**: Sidebar + chat (sources hidden)
- **Mobile**: Chat only (sidebar behind drawer; coming soon)
- **Streaming**: Real-time token-by-token display
- **Sources**: Live card display with relevance scores, snippets, page numbers

## Configuration

Copy `.env.example` to `.env` and edit:

```bash
cp .env.example .env
```

### Common Settings

```env
# Server
API_HOST=127.0.0.1              # Change to 0.0.0.0 to expose (requires auth)
API_PORT=8000

# LLM
LLM_N_CTX=2048                  # Context window (tokens)
LLM_N_THREADS=4                 # CPU threads for inference
LLM_N_GPU_LAYERS=16             # GPU layers (0 = CPU only; 16 = auto-detect on Apple Silicon)
LLM_MAX_TOKENS=512              # Max response length
LLM_TEMPERATURE=0.1             # Lower = deterministic, higher = creative

# Retrieval
TOP_K_RETRIEVAL=5               # Number of chunks to retrieve
CHUNK_SIZE=400                  # Chunk size (tokens, roughly)
CHUNK_OVERLAP=60                # Overlap between chunks

# Embeddings
EMBED_MODEL=nomic-ai/nomic-embed-text-v1.5-Q
EMBED_DIM=768

# TTS (optional)
TTS_VOICE=af_sarah              # Voice ID
TTS_SPEED=1.0
TTS_CACHE_MAX_FILES=200
TTS_CACHE_MAX_BYTES=209715200   # 200 MB

# Upload Limits
MAX_UPLOAD_BYTES=52428800       # 50 MB
```

See `.env.example` for all options.

## Usage

### Uploading Documents

1. **Drag & drop** PDF/TXT/MD files into the "Drop notes here" zone
2. **Or click** the zone to browse
3. **Or copy** files into `notes/` folder (auto-watched)
4. Ingest log shows status (chunks count, errors, duplicates)

### Querying

1. Type a question in the input field
2. Press Enter or click the send button
3. Wait for streaming response
4. View sources on the right (desktop) or below (mobile/tablet)
5. Click the speaker icon 🔊 on any response to read it aloud (TTS)

### Adding URLs

1. Paste a web URL or YouTube link in the "Paste URL" field
2. Click "Add" or press Enter
3. Ingest log shows progress

### Deleting Documents

1. Click the ✕ button on any document in the "Ingested Docs" list
2. Confirm the deletion
3. Document is removed from the vector DB

## Architecture

```
┌─ Frontend (React + Vite)
│  └─ Streaming API (/api/stream)
│  └─ File Upload (/api/ingest/file)
│  └─ URL Ingest (/api/ingest/url)
│
├─ Backend (FastAPI)
│  ├─ Embeddings (fastembed + nomic-1.5-Q)
│  ├─ LLM (llama-cpp-python + LFM-1.2B GGUF)
│  ├─ Vector DB (LanceDB, local SQLite-like)
│  ├─ Web Scraper (trafilatura + httpx)
│  └─ TTS (kokoro-onnx, optional)
│
└─ Data Storage
   ├─ models/ (GGUF, ONNX, bins)
   ├─ data/lancedb/ (vector DB)
   ├─ data/tts_cache/ (WAV audio)
   └─ notes/ (watched auto-ingest)
```

## API Endpoints

All endpoints require **no authentication** (local-only by default).

### Query

```
GET /api/stream?query=<string>&top_k=<int>

Server-Sent Events (SSE) stream:
  type: 'sources' | 'token' | 'error'
```

### Ingest

```
POST /api/ingest/file           (multipart/form-data)
POST /api/ingest/url            (JSON: { url })
POST /api/ingest/text           (JSON: { text, source, page? })
```

### Documents

```
GET  /api/docs                  (list + status)
DEL  /api/docs/{doc_id}
```

### TTS

```
POST /api/tts                   (JSON: { text, voice?, speed? })
                                 (returns WAV bytes)
```

### Health

```
GET  /api/health
```

## Troubleshooting

### "Model not found"

```
ERROR: Model not found at models/LFM2-1.2B-RAG-Q4_K_M.gguf
```

**Fix:**
1. Download `LFM2-1.2B-RAG-Q4_K_M.gguf` from HuggingFace
2. Place in `models/` directory
3. Re-run `bash start.sh`

Or use a different model and update `LLM_MODEL_PATH` in `backend/config.py`.

### "No documents ingested yet"

- Check the "Ingested Docs" list in the UI
- Check `data/lancedb/` exists and has files
- Check the ingest log for errors during upload

### Server won't start

1. **Port in use**: Change `API_PORT=8001` in `.env` and re-run
2. **Python not found**: Ensure venv is activated: `source .venv/bin/activate`
3. **ONNX error**: Install llama-cpp-python: `pip install llama-cpp-python>=0.3.28`

### Slow inference

- Check `LLM_N_CTX` (lower = faster)
- Check `LLM_N_THREADS` (increase if you have many cores)
- Check `TOP_K_RETRIEVAL` (lower = fewer chunks = faster)

### TTS crashes or doesn't work

TTS is optional. If `kokoro-onnx` is not installed:
- Remove TTS model files from `models/`
- Restart; app continues without TTS

### "Context window overflow" warning

Your question + context is too large. Try:
- Reduce `TOP_K_RETRIEVAL` (fewer chunks)
- Reduce `CHUNK_SIZE` (smaller chunks)
- Reduce `LLM_N_CTX` (smaller context; may hurt quality)

## Development

### File Structure

```
.
├── backend/              # FastAPI app
│  ├── main.py            # Entry point
│  ├── config.py          # Env vars
│  ├── llm.py             # LLM inference + RAG logic
│  ├── embeddings.py      # Embeddings via fastembed
│  ├── vectordb.py        # LanceDB interface
│  ├── ingest.py          # Document processing
│  ├── scraper.py         # Web scraping
│  ├── tts.py             # Kokoro TTS
│  ├── watcher.py         # Auto-ingest from notes/
│  └── routers/           # API endpoints
├── frontend/             # React + Vite
│  ├── src/
│  │  ├── App.tsx         # Main UI
│  │  ├── api.ts          # API client
│  │  └── styles/         # CSS
│  └── vite.config.ts
├── models/               # GGUF, ONNX (gitignored)
├── data/                 # Vector DB, caches (gitignored)
├── notes/                # User docs for auto-ingest
├── requirements.txt      # Python deps
└── start.sh              # Startup script
```

### Running in Dev Mode

```bash
# Terminal 1: Backend
source .venv/bin/activate
python -m backend.main

# Terminal 2: Frontend
cd frontend && npm run dev
```

Open `http://localhost:5173` (frontend dev proxy → backend:8000).

### Running Tests

```bash
pytest tests/ -v
```

(Currently no tests; contributions welcome!)

## Security

- **Localhost-only by default**: `API_HOST=127.0.0.1`
- **No auth required** for local-only deployments
- **SSRF blocking**: Private IPs, cloud metadata blocked for web ingestion
- **URL validation**: Scheme, hostname, DNS resolution checks

**If exposing to network:**
- Set `OPENBOOK_API_KEY` in `.env` (implement in backend if needed)
- Use reverse proxy (nginx) with authentication
- Keep `API_HOST=127.0.0.1` and proxy from another machine

## Performance Tips

1. **Faster inference**:
   - Reduce `LLM_N_CTX` (e.g., 1024)
   - Increase `LLM_N_THREADS` (up to # of CPU cores)
   - Use Q3 GGUF instead of Q4 (smaller, faster)

2. **Faster ingestion**:
   - Increase `LLM_N_BATCH` (e.g., 1024)
   - Use SSD for `data/` directory

3. **Lower memory usage**:
   - Reduce `CHUNK_SIZE` (e.g., 256)
   - Reduce `TOP_K_RETRIEVAL` (e.g., 3)

## License

MIT

## Acknowledgments

- LFM-1.2B by Liquid AI
- nomic-embed-text by Nomic AI
- LanceDB by Lance
- Kokoro TTS by The White Eagle
- FastAPI, React, Vite communities
