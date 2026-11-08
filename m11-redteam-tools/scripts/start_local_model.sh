#!/usr/bin/env bash
# Serve Qwen2.5-0.5B-Instruct (GGUF q4_k_m, Apache-2.0, ~490 MB) on 127.0.0.1:8081 with an
# OpenAI-compatible API, using llama-cpp-python's server. Fits a free 2-core, 8 GB Codespace.
# First run installs llama-cpp-python (builds from source: a few minutes) and downloads the model.
set -euo pipefail
pip install -q "llama-cpp-python[server]==0.3.36" "huggingface_hub>=1.0"
python - <<'PY'
from huggingface_hub import hf_hub_download
p = hf_hub_download("Qwen/Qwen2.5-0.5B-Instruct-GGUF", "qwen2.5-0.5b-instruct-q4_k_m.gguf",
                    revision="9217f5db79a29953eb74d5343926648285ec7e67")
open("/tmp/qwen-gguf-path", "w").write(p)
PY
nohup python -m llama_cpp.server --model "$(cat /tmp/qwen-gguf-path)" --model_alias qwen2.5-0.5b-instruct \
  --host 127.0.0.1 --port 8081 --n_ctx 4096 > /tmp/local-model.log 2>&1 &
for _ in $(seq 1 120); do
  curl -fsS http://127.0.0.1:8081/v1/models > /dev/null 2>&1 && { echo "local model up on http://127.0.0.1:8081/v1"; exit 0; }
  sleep 1
done
echo "local model did not start; see /tmp/local-model.log" >&2; exit 1
