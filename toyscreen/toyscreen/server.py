"""Local HTTP endpoint for ToyScreen's recruiter chat, used as the Module 11 target.

    POST /chat   {"message": "...", "candidate_id": "C-001"}  ->  {"reply": "..."}
    POST /v1/chat/completions   OpenAI-compatible wrapper around /chat (the last user
         message is the chat message), so tools that speak the OpenAI chat API (PyRIT's
         OpenAIChatTarget, promptfoo's openai provider, garak's openai-compatible
         generator) can target ToyScreen. Any API key is accepted and ignored.
    GET  /v1/models
    POST /reset  -> {"ok": true}
    GET  /health -> {"ok": true, "flags": {...}}

It binds to 127.0.0.1 only. In a Codespace, leave any forwarded port Private.
"""
from __future__ import annotations

import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


def serve(app, port: int = 8080, host: str = "127.0.0.1") -> None:
    lock = threading.Lock()

    class Handler(BaseHTTPRequestHandler):
        def _send(self, code: int, body: dict) -> None:
            data = json.dumps(body).encode()
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self):
            if self.path == "/health":
                return self._send(200, {"ok": True, "backend": app.llm.name, "flags": vars(app.flags)})
            if self.path == "/v1/models":
                return self._send(200, {"object": "list", "data": [{"id": "toyscreen", "object": "model"}]})
            self._send(404, {"error": "not found"})

        def do_POST(self):
            length = int(self.headers.get("Content-Length") or 0)
            try:
                body = json.loads(self.rfile.read(length) or b"{}")
            except json.JSONDecodeError:
                return self._send(400, {"error": "invalid JSON"})
            with lock:
                if self.path == "/chat":
                    reply = app.chat(str(body.get("message", "")), str(body.get("candidate_id", "C-001")))
                    return self._send(200, {"reply": reply})
                if self.path == "/v1/chat/completions":
                    msgs = body.get("messages") or []
                    users = [m for m in msgs if m.get("role") == "user"]
                    content = users[-1].get("content", "") if users else ""
                    if isinstance(content, list):  # OpenAI content parts
                        content = " ".join(p.get("text", "") for p in content if isinstance(p, dict))
                    reply = app.chat(str(content), str(body.get("candidate_id", "C-001")))
                    return self._send(200, {
                        "id": f"toyscreen-{int(time.time() * 1000)}", "object": "chat.completion",
                        "created": int(time.time()), "model": body.get("model", "toyscreen"),
                        "choices": [{"index": 0, "finish_reason": "stop",
                                     "message": {"role": "assistant", "content": reply}}],
                        "usage": {"prompt_tokens": len(str(content).split()),
                                  "completion_tokens": len(reply.split()),
                                  "total_tokens": len(str(content).split()) + len(reply.split())}})
                if self.path == "/reset":
                    app.reset()
                    return self._send(200, {"ok": True})
            self._send(404, {"error": "not found"})

        def log_message(self, fmt, *args):  # keep the terminal quiet; requests are logged by ToyScreen
            pass

    httpd = ThreadingHTTPServer((host, port), Handler)
    print(f"ToyScreen chat endpoint on http://{host}:{port}/chat (backend={app.llm.name})", flush=True)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
