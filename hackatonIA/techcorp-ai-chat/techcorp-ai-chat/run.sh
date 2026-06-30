#!/usr/bin/env bash
# run.sh — one command to bring up the whole stack.
#   1. deploy the clean model to Ollama (if installed)
#   2. start the FastAPI gateway + chat UI on http://localhost:8500
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$HERE"

export MODEL="${MODEL:-phi35-financial-clean}"

echo "==> Installing Python deps..."
pip install -q -r app/requirements.txt

if command -v ollama >/dev/null 2>&1; then
  bash infra/deploy.sh || echo "   (model deploy step had warnings — continuing)"
else
  echo "⚠  Ollama not found. The UI will start but show 'offline' until you"
  echo "   install Ollama (https://ollama.com/download) and run: bash infra/deploy.sh"
fi

echo "==> Starting gateway on http://localhost:8500  (Ctrl+C to stop)"
exec python -m uvicorn app.server:app --host 0.0.0.0 --port 8500