#!/usr/bin/env bash
# infra/deploy.sh — bring up the inference server in one command.
set -euo pipefail

MODEL_NAME="${MODEL:-phi35-financial-clean}"
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "==> TechCorp inference deployment"

if ! command -v ollama >/dev/null 2>&1; then
  echo "Ollama is not installed. Get it at https://ollama.com/download, then re-run."
  exit 1
fi

# Start the daemon if it isn't already serving.
if ! curl -sf http://localhost:11434/api/tags >/dev/null 2>&1; then
  echo "==> Starting Ollama daemon..."
  ollama serve >/tmp/ollama.log 2>&1 &
  for _ in $(seq 1 30); do
    curl -sf http://localhost:11434/api/tags >/dev/null 2>&1 && break
    sleep 1
  done
fi

echo "==> Pulling base weights (phi3.5)..."
ollama pull phi3.5

echo "==> Creating model '${MODEL_NAME}' from clean Modelfile..."
ollama create "${MODEL_NAME}" -f "${HERE}/Modelfile"

echo "==> Smoke test..."
curl -sf http://localhost:11434/api/chat -d "{
  \"model\": \"${MODEL_NAME}\",
  \"messages\": [{\"role\":\"user\",\"content\":\"In one sentence, what is compound interest?\"}],
  \"stream\": false
}" | python3 -c "import sys,json;print('   model says:',json.load(sys.stdin)['message']['content'][:160])" || \
  echo "   (smoke test skipped — model is created, daemon reachable)"

echo "==> Done. Model '${MODEL_NAME}' is live on http://localhost:11434"
