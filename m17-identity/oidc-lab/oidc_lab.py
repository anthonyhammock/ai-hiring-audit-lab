"""A minimal OAuth 2.0 / OpenID Connect identity provider and client, for Module 17 Lesson 02.

TRAINING SOFTWARE WITH SWITCHABLE WEAKNESSES. FICTIONAL USERS ONLY. NOT FOR PRODUCTION.

    python oidc_lab.py serve        # IdP on 127.0.0.1:9000, client app on 127.0.0.1:9001
    python oidc_lab.py selftest     # drive every flow and negative test headlessly (works in Colab)

IdP (port 9000)
    /.well-known/openid-configuration, /jwks, /authorize, /token
    /admin                 toggles: wildcard redirect matching, PKCE required, refresh-token rotation
    /lab/issue-for-client-b   issues a correctly signed ID Token whose aud is "client-b"
Client app (port 9001)
    /            flow trace (every front-channel and back-channel message, with secrets shortened)
    /login       starts authorization code + PKCE (S256) with state and nonce
    /callback    checks state, redeems the code, validates the ID Token (signature, iss, aud, exp, nonce)
    /settings    toggles: validate aud, validate nonce, send a wrong code_verifier
    /test/aud, /test/replay-nonce, /test/refresh   the Lesson 02 negative tests

Users: alice / bob, password "lab-password" (fictional). Client secret: "demo-not-a-real-secret".
Section references in the trace point to RFC 6749 (OAuth 2.0), RFC 7636 (PKCE), RFC 9700
(OAuth 2.0 Security Best Current Practice) and OpenID Connect Core 1.0.
"""
from __future__ import annotations

import base64
import hashlib
import html
import json
import os
import secrets
import sys
import threading
import time
import urllib.parse
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import jwt
from cryptography.hazmat.primitives.asymmetric import rsa

IDP_PORT, CLIENT_PORT = int(os.environ.get("IDP_PORT", 9000)), int(os.environ.get("CLIENT_PORT", 9001))


def public_url(port: int) -> str:
    """Browser-facing URL. In a Codespace, forwarded ports live on *.app.github.dev."""
    cs, dom = os.environ.get("CODESPACE_NAME"), os.environ.get("GITHUB_CODESPACES_PORT_FORWARDING_DOMAIN")
    if cs and dom:
        return f"https://{cs}-{port}.{dom}"
    return f"http://127.0.0.1:{port}"


IDP_PUBLIC, CLIENT_PUBLIC = public_url(IDP_PORT), public_url(CLIENT_PORT)
IDP_BACKCHANNEL = f"http://127.0.0.1:{IDP_PORT}"
ISSUER = IDP_PUBLIC
KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)
KID = "lab-key-1"
USERS = {"alice": "lab-password", "bob": "lab-password"}


def b64url(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).rstrip(b"=").decode()


def short(v: str | None) -> str:
    return v if not v or len(v) < 16 else v[:8] + "…" + v[-4:]


# ------------------------------------------------------------------------------- IdP state
IDP = {
    "settings": {"wildcard_redirects": False, "require_pkce": True, "refresh_rotation": False},
    "clients": {
        "client-a": {"secret": "demo-not-a-real-secret", "redirect_uris": [f"{CLIENT_PUBLIC}/callback"]},
        "client-b": {"secret": "demo-not-a-real-secret-b", "redirect_uris": ["http://127.0.0.1:9999/callback"]},
    },
    "codes": {},      # code -> grant
    "refresh": {},    # refresh token -> {"sub", "client_id", "family", "active"}
}


def redirect_allowed(client: dict, uri: str) -> bool:
    if IDP["settings"]["wildcard_redirects"]:
        # Deliberately weak: prefix match on the registered URI's scheme and host only.
        return any(uri.startswith(r.split("/callback")[0].rsplit(":", 1)[0]) for r in client["redirect_uris"])
    return uri in client["redirect_uris"]  # exact string match (RFC 9700 section 4.1.3)


def id_token(sub: str, aud: str, nonce: str | None, lifetime: int = 300) -> str:
    now = int(time.time())
    claims = {"iss": ISSUER, "sub": sub, "aud": aud, "iat": now, "exp": now + lifetime, "auth_time": now}
    if nonce:
        claims["nonce"] = nonce
    return jwt.encode(claims, KEY, algorithm="RS256", headers={"kid": KID})


def jwks() -> dict:
    n = KEY.public_key().public_numbers()
    to_b = lambda i: b64url(i.to_bytes((i.bit_length() + 7) // 8, "big"))
    return {"keys": [{"kty": "RSA", "use": "sig", "alg": "RS256", "kid": KID, "n": to_b(n.n), "e": to_b(n.e)}]}


def new_refresh(sub: str, client_id: str, family: str | None = None) -> str:
    rt = secrets.token_urlsafe(24)
    IDP["refresh"][rt] = {"sub": sub, "client_id": client_id, "family": family or rt, "active": True}
    return rt


def token_endpoint(form: dict) -> tuple[int, dict]:
    cid, csec = form.get("client_id"), form.get("client_secret")
    client = IDP["clients"].get(cid or "")
    if not client or client["secret"] != csec:
        return 401, {"error": "invalid_client"}
    gt = form.get("grant_type")
    if gt == "authorization_code":
        grant = IDP["codes"].pop(form.get("code", ""), None)  # single use (RFC 6749 section 4.1.2)
        if not grant or grant["client_id"] != cid or grant["expires"] < time.time():
            return 400, {"error": "invalid_grant", "error_description": "unknown, used or expired code"}
        if grant["redirect_uri"] != form.get("redirect_uri"):
            return 400, {"error": "invalid_grant", "error_description": "redirect_uri mismatch"}
        if grant.get("code_challenge"):
            verifier = form.get("code_verifier", "")
            if b64url(hashlib.sha256(verifier.encode()).digest()) != grant["code_challenge"]:
                return 400, {"error": "invalid_grant", "error_description": "PKCE verification failed (RFC 7636 section 4.6)"}
        return 200, {"token_type": "Bearer", "access_token": secrets.token_urlsafe(24), "expires_in": 300,
                     "id_token": id_token(grant["sub"], cid, grant.get("nonce")),
                     "refresh_token": new_refresh(grant["sub"], cid)}
    if gt == "refresh_token":
        rec = IDP["refresh"].get(form.get("refresh_token", ""))
        if not rec or rec["client_id"] != cid:
            return 400, {"error": "invalid_grant", "error_description": "unknown refresh token"}
        if not rec["active"]:
            for r in IDP["refresh"].values():  # reuse detected: revoke the whole family (RFC 9700 section 4.14.2)
                if r["family"] == rec["family"]:
                    r["active"] = False
            return 400, {"error": "invalid_grant", "error_description": "refresh token reuse detected; family revoked"}
        body = {"token_type": "Bearer", "access_token": secrets.token_urlsafe(24), "expires_in": 300}
        if IDP["settings"]["refresh_rotation"]:
            rec["active"] = False
            body["refresh_token"] = new_refresh(rec["sub"], cid, rec["family"])
        return 200, body
    return 400, {"error": "unsupported_grant_type"}


# ------------------------------------------------------------------------------- client state
CLIENT = {
    "settings": {"validate_aud": True, "validate_nonce": True, "wrong_verifier": False},
    "pending": {},       # state -> {"nonce", "verifier"}
    "used_nonces": set(),
    "trace": [],
    "last": {},          # last tokens
}


def trace(kind: str, detail: dict, ref: str = "") -> None:
    CLIENT["trace"].append({"t": time.strftime("%H:%M:%S"), "kind": kind, "ref": ref,
                            "detail": {k: short(v) if isinstance(v, str) and k != "error" else v
                                       for k, v in detail.items()}})


def validate_id_token(token: str, expected_nonce: str | None) -> dict:
    """OIDC Core 1.0 section 3.1.3.7 checks. Raises ValueError with the failing check."""
    key = jwt.PyJWK(jwks()["keys"][0]).key
    try:
        claims = jwt.decode(token, key, algorithms=["RS256"], issuer=ISSUER,
                            audience="client-a" if CLIENT["settings"]["validate_aud"] else None,
                            options={"verify_aud": CLIENT["settings"]["validate_aud"], "require": ["exp", "iat", "iss"]})
    except jwt.InvalidAudienceError:
        raise ValueError("aud check failed: token was issued to a different client")
    except jwt.ExpiredSignatureError:
        raise ValueError("exp check failed: token expired")
    except jwt.InvalidIssuerError:
        raise ValueError("iss check failed")
    except jwt.InvalidTokenError as e:
        raise ValueError(f"signature or format check failed: {e}")
    if CLIENT["settings"]["validate_nonce"]:
        if claims.get("nonce") != expected_nonce:
            raise ValueError("nonce check failed: does not match this login")
        if claims["nonce"] in CLIENT["used_nonces"]:
            raise ValueError("nonce check failed: nonce already used (replay)")
        CLIENT["used_nonces"].add(claims["nonce"])
    return claims


def http_post(url: str, form: dict) -> tuple[int, dict]:
    req = urllib.request.Request(url, data=urllib.parse.urlencode(form).encode(), method="POST",
                                 headers={"Content-Type": "application/x-www-form-urlencoded"})
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read() or b"{}")


def start_login() -> str:
    state, nonce, verifier = secrets.token_urlsafe(16), secrets.token_urlsafe(16), secrets.token_urlsafe(48)
    CLIENT["pending"][state] = {"nonce": nonce, "verifier": verifier}
    q = {"response_type": "code", "client_id": "client-a", "redirect_uri": f"{CLIENT_PUBLIC}/callback",
         "scope": "openid", "state": state, "nonce": nonce,
         "code_challenge": b64url(hashlib.sha256(verifier.encode()).digest()), "code_challenge_method": "S256"}
    trace("authorization request (front channel)", q, "RFC 6749 4.1.1; RFC 7636 4.3; OIDC Core 3.1.2.1")
    return f"{IDP_PUBLIC}/authorize?{urllib.parse.urlencode(q)}"


def finish_login(params: dict) -> tuple[bool, str]:
    trace("authorization response (front channel)", params, "RFC 6749 4.1.2")
    pend = CLIENT["pending"].pop(params.get("state", ""), None)
    if not pend:
        return False, "state check failed: unknown or reused state (RFC 9700 4.7.1)"
    if "error" in params:
        return False, f"IdP returned error: {params['error']}"
    verifier = "wrong-" + pend["verifier"] if CLIENT["settings"]["wrong_verifier"] else pend["verifier"]
    form = {"grant_type": "authorization_code", "code": params.get("code", ""), "redirect_uri": f"{CLIENT_PUBLIC}/callback",
            "client_id": "client-a", "client_secret": IDP["clients"]["client-a"]["secret"], "code_verifier": verifier}
    trace("token request (back channel)", form, "RFC 6749 4.1.3; RFC 7636 4.5")
    status, body = http_post(f"{IDP_BACKCHANNEL}/token", form)
    trace(f"token response {status}", body, "RFC 6749 4.1.4; OIDC Core 3.1.3.3")
    if status != 200:
        return False, f"token request rejected: {body.get('error_description', body)}"
    try:
        claims = validate_id_token(body["id_token"], pend["nonce"])
    except ValueError as e:
        trace("ID Token validation FAILED", {"error": str(e)}, "OIDC Core 3.1.3.7")
        return False, str(e)
    CLIENT["last"] = {**body, "nonce": pend["nonce"]}
    trace("ID Token validation passed", {"sub": claims["sub"], "aud": claims["aud"], "iss": claims["iss"]},
          "OIDC Core 3.1.3.7")
    return True, f"signed in as {claims['sub']}"


def test_aud() -> str:
    with urllib.request.urlopen(f"{IDP_BACKCHANNEL}/lab/issue-for-client-b", timeout=10) as r:
        tok = json.loads(r.read())["id_token"]
    try:
        validate_id_token(tok, jwt.decode(tok, options={"verify_signature": False}).get("nonce"))
        msg = "ACCEPTED a token issued to client-b (aud validation is off: this is the vulnerability)"
    except ValueError as e:
        msg = f"rejected: {e}"
    trace("negative test: ID Token for client-b", {"result": msg}, "OIDC Core 3.1.3.7 step 3")
    return msg


def test_replay() -> str:
    last = CLIENT["last"]
    if not last:
        return "sign in first"
    try:
        validate_id_token(last["id_token"], last["nonce"])
        msg = "ACCEPTED a replayed ID Token (nonce validation is off: this is the vulnerability)"
    except ValueError as e:
        msg = f"rejected: {e}"
    trace("negative test: replayed ID Token", {"result": msg}, "OIDC Core 3.1.3.7 step 11; 15.5.2")
    return msg


def test_refresh() -> str:
    last = CLIENT["last"]
    if not last.get("refresh_token"):
        return "sign in first"
    form = {"grant_type": "refresh_token", "refresh_token": last["refresh_token"], "client_id": "client-a",
            "client_secret": IDP["clients"]["client-a"]["secret"]}
    s1, b1 = http_post(f"{IDP_BACKCHANNEL}/token", form)
    s2, b2 = http_post(f"{IDP_BACKCHANNEL}/token", form)
    if b1.get("refresh_token"):
        CLIENT["last"]["refresh_token"] = b1["refresh_token"]
    msg = (f"first use: {s1} ({'new refresh token issued' if 'refresh_token' in b1 else b1.get('error', 'ok')}); "
           f"second use of the SAME old token: {s2} ({b2.get('error_description', 'accepted')})")
    trace("negative test: refresh token reuse", {"result": msg}, "RFC 9700 4.14.2; RFC 6749 6")
    return msg


# ------------------------------------------------------------------------------- HTTP
def page(title: str, body: str) -> bytes:
    return (f"<!doctype html><html><head><meta charset='utf-8'><title>{html.escape(title)}</title>"
            "<style>body{font-family:system-ui,sans-serif;max-width:900px;margin:2em auto;padding:0 1em}"
            "pre{background:#f4f4f4;padding:.5em;overflow:auto}</style></head><body>"
            f"<p><strong>FICTIONAL LAB.</strong> Not for production.</p>{body}</body></html>").encode()


def form_bool(d: dict, k: str) -> bool:
    return d.get(k, ["off"])[0] == "on"


class Base(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def send(self, code: int, body: bytes, ctype: str = "text/html", headers: dict | None = None):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        for k, v in (headers or {}).items():
            self.send_header(k, v)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def redirect(self, url: str):
        self.send(302, b"", headers={"Location": url})

    def form(self) -> dict:
        n = int(self.headers.get("Content-Length") or 0)
        return urllib.parse.parse_qs(self.rfile.read(n).decode())


class IdPHandler(Base):
    def do_GET(self):
        u = urllib.parse.urlparse(self.path)
        q = {k: v[0] for k, v in urllib.parse.parse_qs(u.query).items()}
        if u.path == "/.well-known/openid-configuration":
            return self.send(200, json.dumps({
                "issuer": ISSUER, "authorization_endpoint": f"{IDP_PUBLIC}/authorize",
                "token_endpoint": f"{IDP_PUBLIC}/token", "jwks_uri": f"{IDP_PUBLIC}/jwks",
                "response_types_supported": ["code"], "subject_types_supported": ["public"],
                "id_token_signing_alg_values_supported": ["RS256"], "code_challenge_methods_supported": ["S256"],
                "grant_types_supported": ["authorization_code", "refresh_token"]}).encode(), "application/json")
        if u.path == "/jwks":
            return self.send(200, json.dumps(jwks()).encode(), "application/json")
        if u.path == "/lab/issue-for-client-b":
            return self.send(200, json.dumps({"id_token": id_token("alice", "client-b", secrets.token_urlsafe(8))}).encode(),
                             "application/json")
        if u.path == "/authorize":
            client = IDP["clients"].get(q.get("client_id", ""))
            if not client or not redirect_allowed(client, q.get("redirect_uri", "")):
                # Never redirect to an unregistered URI (RFC 6749 4.1.2.1)
                return self.send(400, page("Error", f"<h1>invalid redirect_uri or client</h1><pre>{html.escape(q.get('redirect_uri', ''))}</pre>"))
            if IDP["settings"]["require_pkce"] and q.get("code_challenge_method") != "S256":
                return self.redirect(q["redirect_uri"] + "?" + urllib.parse.urlencode(
                    {"error": "invalid_request", "error_description": "PKCE S256 required", "state": q.get("state", "")}))
            hidden = "".join(f"<input type=hidden name='{html.escape(k)}' value='{html.escape(v)}'>" for k, v in q.items())
            return self.send(200, page("Sign in", f"<h1>Lab IdP sign-in</h1><form method=post action='/authorize'>{hidden}"
                                       "User <input name=username value=alice> Password <input name=password type=password value=lab-password> "
                                       "<button>Sign in</button></form><p>Redirect URI requested: "
                                       f"<code>{html.escape(q.get('redirect_uri', ''))}</code></p>"))
        if u.path == "/admin":
            s = IDP["settings"]
            boxes = "".join(f"<label><input type=checkbox name={k} {'checked' if v else ''}> {k}</label><br>" for k, v in s.items())
            return self.send(200, page("IdP admin", f"<h1>IdP settings</h1><form method=post action='/admin'>{boxes}"
                                       "<button>Save</button></form><h2>Registered clients</h2>"
                                       f"<pre>{html.escape(json.dumps({k: v['redirect_uris'] for k, v in IDP['clients'].items()}, indent=1))}</pre>"))
        self.send(404, page("Not found", "<h1>404</h1>"))

    def do_POST(self):
        u = urllib.parse.urlparse(self.path)
        f = self.form()
        if u.path == "/token":
            code, body = token_endpoint({k: v[0] for k, v in f.items()})
            return self.send(code, json.dumps(body).encode(), "application/json", {"Cache-Control": "no-store"})
        if u.path == "/admin":
            for k in IDP["settings"]:
                IDP["settings"][k] = form_bool(f, k)
            return self.redirect(f"{IDP_PUBLIC}/admin")
        if u.path == "/authorize":
            q = {k: v[0] for k, v in f.items()}
            client = IDP["clients"].get(q.get("client_id", ""))
            if not client or not redirect_allowed(client, q.get("redirect_uri", "")):
                return self.send(400, page("Error", "<h1>invalid redirect_uri or client</h1>"))
            if USERS.get(q.pop("username", "")) != q.pop("password", None):
                return self.send(401, page("Error", "<h1>wrong username or password</h1>"))
            code = secrets.token_urlsafe(24)
            IDP["codes"][code] = {"client_id": q["client_id"], "redirect_uri": q["redirect_uri"], "sub": "alice",
                                  "nonce": q.get("nonce"), "code_challenge": q.get("code_challenge"),
                                  "expires": time.time() + 60}
            return self.redirect(q["redirect_uri"] + "?" + urllib.parse.urlencode({"code": code, "state": q.get("state", ""),
                                                                                  "iss": ISSUER}))
        self.send(404, b"")


class ClientHandler(Base):
    def do_GET(self):
        u = urllib.parse.urlparse(self.path)
        q = {k: v[0] for k, v in urllib.parse.parse_qs(u.query).items()}
        if u.path == "/login":
            return self.redirect(start_login())
        if u.path == "/callback":
            ok, msg = finish_login(q)
            return self.send(200 if ok else 400, page("Callback", f"<h1>{'OK' if ok else 'Rejected'}</h1><p>{html.escape(msg)}</p><a href='/'>Flow trace</a>"))
        if u.path.startswith("/test/"):
            fn = {"/test/aud": test_aud, "/test/replay-nonce": test_replay, "/test/refresh": test_refresh}.get(u.path)
            if fn:
                return self.send(200, page("Test", f"<p>{html.escape(fn())}</p><a href='/'>Flow trace</a>"))
        if u.path == "/settings":
            s = CLIENT["settings"]
            boxes = "".join(f"<label><input type=checkbox name={k} {'checked' if v else ''}> {k}</label><br>" for k, v in s.items())
            return self.send(200, page("Client settings", f"<form method=post action='/settings'>{boxes}<button>Save</button></form>"))
        if u.path == "/":
            rows = "".join(f"<h3>{html.escape(e['t'])} {html.escape(e['kind'])}</h3><p><em>{html.escape(e['ref'])}</em></p>"
                           f"<pre>{html.escape(json.dumps(e['detail'], indent=1))}</pre>" for e in CLIENT["trace"])
            return self.send(200, page("Client", "<h1>Lab client: flow trace</h1>"
                                       "<p><a href='/login'>Sign in</a> · <a href='/settings'>Client settings</a> · "
                                       f"<a href='{IDP_PUBLIC}/admin'>IdP settings</a> · <a href='/test/aud'>Test: token for client B</a> · "
                                       "<a href='/test/replay-nonce'>Test: replay ID Token</a> · <a href='/test/refresh'>Test: refresh reuse</a></p>"
                                       + (rows or "<p>No messages yet.</p>")))
        self.send(404, page("Not found", "<h1>404</h1>"))

    def do_POST(self):
        if self.path == "/settings":
            f = self.form()
            for k in CLIENT["settings"]:
                CLIENT["settings"][k] = form_bool(f, k)
            return self.redirect(f"{CLIENT_PUBLIC}/settings")
        self.send(404, b"")


def serve_background() -> list[ThreadingHTTPServer]:
    servers = [ThreadingHTTPServer(("127.0.0.1", IDP_PORT), IdPHandler),
               ThreadingHTTPServer(("127.0.0.1", CLIENT_PORT), ClientHandler)]
    for s in servers:
        threading.Thread(target=s.serve_forever, daemon=True).start()
    return servers


# ------------------------------------------------------------------------------- headless self-test
def browser_login(wrong_redirect: str | None = None) -> tuple[bool, str]:
    """Play the browser: follow /login, submit the sign-in form, deliver the code to /callback."""
    url = start_login()
    if wrong_redirect:
        url = url.replace(urllib.parse.quote(f"{CLIENT_PUBLIC}/callback", safe=""), urllib.parse.quote(wrong_redirect, safe=""))
    q = {k: v[0] for k, v in urllib.parse.parse_qs(urllib.parse.urlparse(url).query).items()}
    q.update(username="alice", password="lab-password")

    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, *a, **k):
            return None
    opener = urllib.request.build_opener(NoRedirect)
    req = urllib.request.Request(f"{IDP_BACKCHANNEL}/authorize", data=urllib.parse.urlencode(q).encode(), method="POST")
    try:
        opener.open(req, timeout=10)
        return False, "no redirect"
    except urllib.error.HTTPError as e:
        if e.code != 302:
            return False, f"IdP refused: HTTP {e.code}"
        loc = e.headers["Location"]
    if wrong_redirect:
        return True, f"IdP redirected the code to {loc.split('?')[0]}"
    params = {k: v[0] for k, v in urllib.parse.parse_qs(urllib.parse.urlparse(loc).query).items()}
    return finish_login(params)


def selftest() -> int:
    servers = serve_background()
    results = []

    def check(name, cond, detail):
        results.append(cond)
        print(f"[{'PASS' if cond else 'FAIL'}] {name}: {detail}")

    ok, msg = browser_login(); check("code + PKCE (S256) sign-in", ok, msg)
    CLIENT["settings"]["wrong_verifier"] = True
    ok, msg = browser_login(); check("wrong code_verifier is rejected", not ok and "PKCE" in msg, msg)
    CLIENT["settings"]["wrong_verifier"] = False
    ok, msg = browser_login(wrong_redirect="http://127.0.0.1:9001.evil.example/callback")
    check("unregistered redirect URI refused (exact match)", not ok, msg)
    IDP["settings"]["wildcard_redirects"] = True
    ok, msg = browser_login(wrong_redirect="http://127.0.0.1:9001.evil.example/callback")
    check("with wildcard matching ON the IdP sends the code to the attacker URI", ok, msg)
    IDP["settings"]["wildcard_redirects"] = False
    ok, msg = browser_login(); check("sign-in again", ok, msg)
    msg = test_aud(); check("ID Token for client-b rejected on aud", msg.startswith("rejected: aud"), msg)
    CLIENT["settings"]["validate_aud"] = False
    msg = test_aud(); check("with aud validation OFF the client accepts it", msg.startswith("ACCEPTED"), msg)
    CLIENT["settings"]["validate_aud"] = True
    msg = test_replay(); check("replayed ID Token rejected on nonce", "replay" in msg and msg.startswith("rejected"), msg)
    msg = test_refresh(); check("rotation OFF: old refresh token still works", "second use of the SAME old token: 200" in msg, msg)
    IDP["settings"]["refresh_rotation"] = True
    ok, msg = browser_login()
    msg = test_refresh(); check("rotation ON: reused refresh token rejected", "second use of the SAME old token: 400" in msg, msg)
    for s in servers:
        s.shutdown()
    print(f"\n{sum(results)}/{len(results)} checks passed")
    return 0 if all(results) else 1


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "serve"
    if cmd == "selftest":
        sys.exit(selftest())
    serve_background()
    print(f"IdP:    {IDP_PUBLIC}  (admin: {IDP_PUBLIC}/admin)\nClient: {CLIENT_PUBLIC}  (open this one)\nCtrl+C to stop.")
    try:
        while True:
            time.sleep(3600)
    except KeyboardInterrupt:
        pass
