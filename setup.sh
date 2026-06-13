#!/usr/bin/env bash
set -euo pipefail

PYTHON=${PYTHON:-python3}
VENV=".venv"

echo "==> Creating Python virtual environment …"
$PYTHON -m venv $VENV
source $VENV/bin/activate

echo "==> Upgrading pip …"
pip install --upgrade pip wheel setuptools

echo "==> Installing base requirements …"
pip install -r requirements.txt

echo "==> Compiling llama-cpp-python with CPU optimisations …"
ARCH=$(uname -m)
if [[ "$ARCH" == "arm64" ]] && [[ "$(uname)" == "Darwin" ]]; then
  echo "    Detected Apple Silicon — enabling Metal …"
  CMAKE_ARGS="-DLLAMA_METAL=ON -DLLAMA_BLAS=ON -DLLAMA_BLAS_VENDOR=Accelerate" \
    FORCE_CMAKE=1 \
    pip install llama-cpp-python>=0.3.28 --no-binary llama-cpp-python
else
  echo "    Detected x86_64 — enabling AVX2 + OpenMP …"
  CMAKE_ARGS="-DLLAMA_AVX=ON -DLLAMA_AVX2=ON -DLLAMA_F16C=ON -DLLAMA_FMA=ON -DLLAMA_NATIVE=OFF -DGGML_OPENMP=ON" \
    FORCE_CMAKE=1 \
    pip install llama-cpp-python>=0.3.28 --no-binary llama-cpp-python
fi

echo "==> Installing frontend dependencies …"
cd frontend && npm install && npm run build && cd ..

echo ""
echo "==> Setup complete!"
echo ""
echo "Next steps:"
echo "  1. Download LFM2-1.2B-RAG-Q4_K_M.gguf → models/"
echo "     (Liquid AI LFM-1.2B GGUF Q4_K_M from HuggingFace)"
echo "  2. Download kokoro-v0_19.onnx + voices.bin → models/"
echo "     (thewh1teagle/kokoro-onnx on HuggingFace)"
echo "  3. source .venv/bin/activate"
echo "  4. python -m backend.main"
echo "  5. Open http://localhost:8000"
