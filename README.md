# OpenBook

An offline, full-stack RAG study assistant built for low-end hardware (4-core i3, 8 GB RAM).
Ingests PDF notes, stores chunks in a local vector database, and answers questions using a local LLM
— all through a web UI. No Ollama, no Docker, no cloud.

## Architecture

```
study_notes/          ← drop PDFs here (auto-ingested)
processed_notes/      ← ingested PDFs are archived here
chroma_db/            ← ChromaDB persistent store (auto-created)
models/               ← place your GGUF model here
backend/              ← FastAPI server
  ├── config.py
  ├── vector_store.py
  ├── ingest.py
  ├── watcher.py
  ├── llm.py
  ├── main.py
  └── requirements.txt
frontend/             ← React + Vite SPA
  ├── src/
  │   ├── components/
  │   │   ├── Sidebar.jsx
  │   │   ├── AskPanel.jsx
  │   │   ├── StatusBar.jsx
  │   │   ├── LogTicker.jsx
  │   │   └── SourceCard.jsx
  │   ├── App.jsx
  │   ├── App.css
  │   └── main.jsx
  ├── index.html
  ├── package.json
  └── vite.config.js
├── config.py          ← CLI version config
├── vector_store.py    ← CLI version vector store
├── ingest_watcher.py  ← CLI version watcher (standalone)
├── ask.py             ← CLI version (standalone terminal UI)
└── run.sh             ← starts both backend & frontend
```

## Setup

### 1. Virtual environment

```bash
python3 -m venv venv
source venv/bin/activate
```

### 2. Install backend dependencies

```bash
pip install --upgrade pip
CMAKE_ARGS="-DLLAMA_BLAS=ON -DLLAMA_BLAS_VENDOR=OpenBLAS" pip install llama-cpp-python==0.2.75
pip install -r backend/requirements.txt
```

### 3. Download lfm 1.2b rag GGUF model



**Set the path** if using a non-default name:

```bash
export OPENBOOK_MODEL_PATH=models/your-model.gguf
```

### 4. Embeddings (fastembed — no server, no Ollama)

Embeddings use `fastembed` with `nomic-ai/nomic-embed-text-v1.5` (ONNX).
The ONNX model (~270 MB) downloads automatically on first run — the server
may appear to hang for a minute while it downloads. This is normal.

### 5. Install frontend dependencies

```bash
cd frontend
npm install
cd ..
```

## Running

```bash
bash run.sh
```

This starts:
- **Backend** — FastAPI on `http://localhost:8000`
- **Frontend** — Vite dev server on `http://localhost:5173`

Open `http://localhost:5173` in your browser.

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/status` | System health (model loaded, doc count, watcher) |
| `POST` | `/api/ask` | RAG query → `{"query": "..."}` → `{"answer", "sources"}` |
| `GET` | `/api/documents` | List ingested documents with chunk counts |
| `DELETE` | `/api/documents/{filename}` | Remove a document and its chunks |
| `POST` | `/api/ingest` | Manually re-ingest a file → `{"file_path": "..."}` |
| `GET` | `/api/logs` | Last 200 log lines |

## CLI Version (legacy)

The original terminal-based interface is still available:

```bash
# Terminal 1 — watcher
python ingest_watcher.py

# Terminal 2 — interactive Q&A
python ask.py
```

## Configuration

Key settings in `backend/config.py`. Override with environment variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `OPENBOOK_MODEL_PATH` | `models/llama-3.2-1b-instruct-q4_k_m.gguf` | Path to GGUF model |
| `OPENBOOK_N_THREADS` | `4` | CPU threads for inference |
| `OPENBOOK_N_CTX` | `2048` | Context window size |
| `OPENBOOK_N_BATCH` | `512` | Batch size for prompt processing |
| `OPENBOOK_MAX_TOKENS` | `512` | Max generation tokens |
| `OPENBOOK_TEMPERATURE` | `0.1` | Generation temperature |

## Performance tuning for i3 + 8 GB RAM

- **Q4_K_M** quantised model — best quality-to-speed ratio on CPU.
- **4-bit KV cache** (`type_k=2`, `type_v=2`) — reduces KV memory usage by ~75%.
- `n_threads=4` — matches physical cores; hyper-threading adds little for LLM inference.
- `n_ctx=2048` — limits context memory; increase only with headroom.
- Flash Attention **disabled** — no benefit on CPU.
- Embeddings via `fastembed` (ONNX) — no server, no Ollama, runs in-process.
