"""Message inspector: sits between the MCP client and a stdio server and records every
JSON-RPC message in both directions to a JSONL file.

    python trace_proxy.py TRACE_FILE -- python notes_server.py

The agent host uses it when you pass --trace. Read the file with:
    python -c "import json,sys;[print(json.dumps(json.loads(l),indent=1)) for l in open(sys.argv[1])]" trace.jsonl
"""
from __future__ import annotations

import json
import subprocess
import sys
import threading
import time


def main() -> None:
    trace_path = sys.argv[1]
    cmd = sys.argv[sys.argv.index("--") + 1:]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE)
    lock = threading.Lock()
    trace = open(trace_path, "a", encoding="utf-8")

    def record(direction: str, line: bytes) -> None:
        try:
            msg = json.loads(line)
        except ValueError:
            msg = line.decode("utf-8", "replace")
        with lock:
            trace.write(json.dumps({"t": round(time.time(), 3), "dir": direction, "msg": msg}) + "\n")
            trace.flush()

    def pump_out() -> None:
        for line in proc.stdout:
            record("server->client", line)
            sys.stdout.buffer.write(line)
            sys.stdout.buffer.flush()

    threading.Thread(target=pump_out, daemon=True).start()
    for line in sys.stdin.buffer:
        record("client->server", line)
        proc.stdin.write(line)
        proc.stdin.flush()
    proc.stdin.close()
    proc.wait()


if __name__ == "__main__":
    main()
