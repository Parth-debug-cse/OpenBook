#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$PROJECT_DIR"

VENV="$PROJECT_DIR/.venv"
MODEL="models/LFM2-1.2B-RAG-Q4_K_M.gguf"
FRONTEND_DIST="frontend/dist"

# Load .env if it exists, then use API_PORT env var if set, default to 8000
if [ -f .env ]; then
    export $(grep -v '^#' .env | xargs)
fi
PORT="${API_PORT:-8000}"

echo "==> OpenBook Startup"

# 1. Setup if needed
if [ ! -d "$VENV" ]; then
    echo "==> First-time setup — running setup.sh …"
    bash setup.sh
fi

# 2. Check model
if [ ! -f "$MODEL" ]; then
    echo "ERROR: Model not found at $MODEL"
    echo "Download from: https://huggingface.co/bartowski/lfm-1.2b-GGUF"
    echo "Place the GGUF file in models/ then re-run this script."
    exit 1
fi

# 3. Build frontend (skip if dist/ is fresh)
if [ ! -d "$FRONTEND_DIST" ] || [ frontend -nt "$FRONTEND_DIST" ]; then
    echo "==> Building frontend …"
    source "$VENV/bin/activate"
    cd frontend && npm install && npm run build && cd ..
else
    echo "==> Frontend dist/ is up-to-date, skipping rebuild"
fi

# 4. Kill any existing server on the port
PID=$(lsof -ti tcp:$PORT 2>/dev/null || true)
if [ -n "$PID" ]; then
    echo "==> Stopping existing server (PID $PID) …"
    kill "$PID" 2>/dev/null || true
    sleep 2
fi

# 5. Start server
echo "==> Starting OpenBook on http://localhost:$PORT …"
source "$VENV/bin/activate"
python -m backend.main &
SERVER_PID=$!

# 6. Wait for server to be ready
echo -n "==> Waiting for server"
for _ in $(seq 1 40); do
    if curl -s http://127.0.0.1:$PORT/health > /dev/null 2>&1; then
        echo ""
        echo "==> OpenBook is ready at http://localhost:$PORT"
        break
    fi
    echo -n "."
    sleep 1
done

# 7. Open browser
case "$(uname)" in
    Linux)   xdg-open "http://localhost:$PORT" 2>/dev/null || true ;;
    Darwin)  open "http://localhost:$PORT" 2>/dev/null || true ;;
esac

wait $SERVER_PID
