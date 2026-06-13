Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

Write-Host "==> Creating virtual environment ..."
python -m venv .venv
.\.venv\Scripts\Activate.ps1

Write-Host "==> Upgrading pip ..."
pip install --upgrade pip wheel setuptools

Write-Host "==> Installing requirements ..."
pip install -r requirements.txt

Write-Host "==> Compiling llama-cpp-python with AVX2 ..."
$env:CMAKE_ARGS = "-DLLAMA_AVX=ON -DLLAMA_AVX2=ON -DLLAMA_F16C=ON -DLLAMA_FMA=ON"
$env:FORCE_CMAKE = "1"
pip install "llama-cpp-python>=0.3.28" --no-binary llama-cpp-python

Write-Host "==> Building frontend ..."
Set-Location frontend
npm install
npm run build
Set-Location ..

Write-Host ""
Write-Host "==> Done! Place model files in models/ then run:"
Write-Host "    python -m backend.main"
