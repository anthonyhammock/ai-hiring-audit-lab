#!/usr/bin/env bash
# Start ToyScreen's recruiter chat on 127.0.0.1:8080 and wait until it answers.
#   bash scripts/start_lab_assistant.sh              # vulnerable mode (default)
#   TOYSCREEN_MODE=hardened bash scripts/start_lab_assistant.sh
#   TOYSCREEN_BACKEND=llamacpp bash scripts/start_lab_assistant.sh   # real tiny model (slower)
# Stop it with: bash scripts/stop_lab_assistant.sh
set -euo pipefail
here="$(cd "$(dirname "$0")/../.." && pwd)"
port="${TOYSCREEN_PORT:-8080}"
mkdir -p "$here/toyscreen/logs"
cd "$here/toyscreen"
nohup python -m toyscreen serve --port "$port" > logs/server.out 2>&1 &
echo $! > logs/server.pid
for _ in $(seq 1 120); do
  if curl -fsS "http://127.0.0.1:$port/health" > /dev/null 2>&1; then
    echo "ToyScreen is up on http://127.0.0.1:$port (mode=${TOYSCREEN_MODE:-vulnerable}, backend=${TOYSCREEN_BACKEND:-mock})"
    exit 0
  fi
  sleep 1
done
echo "ToyScreen did not start; see toyscreen/logs/server.out" >&2
exit 1
