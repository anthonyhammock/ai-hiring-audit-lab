# OIDC lab: identity provider plus client (Module 17, Lesson 02)

> **TRAINING SOFTWARE WITH SWITCHABLE WEAKNESSES. FICTIONAL USERS ONLY. NOT FOR PRODUCTION.**
> Users `alice` and `bob` (password `lab-password`) and the client secret `demo-not-a-real-secret` are fake. Both servers bind to `127.0.0.1`.

`oidc_lab.py` runs a minimal OpenID Connect identity provider (port 9000) and a confidential client web app (port 9001). It implements authorization code + PKCE (S256), RS256-signed ID Tokens, a JWKS endpoint, refresh tokens with optional rotation and reuse detection, and a flow trace that shows every message with the RFC or OIDC Core section it comes from.

**Why not Keycloak?** Keycloak is the realistic choice, but it is a Java server that needs Docker-in-Docker in the dev container, about a minute to start and several hundred MB of RAM, and its admin UI hides the protocol details this lesson is about. This file is small enough to read in one sitting. If you want Keycloak too, add the `docker-in-docker` dev container feature and follow Keycloak's own "Docker" getting-started guide; that route is not tested here.

## Switches

| Where | Switch | Weak setting | Strong setting | Reference |
|---|---|---|---|---|
| IdP `/admin` | `wildcard_redirects` | on: prefix matching of redirect URIs | off: exact string match | RFC 9700 §4.1.3 |
| IdP `/admin` | `require_pkce` | off | on (S256 only) | RFC 7636; RFC 9700 §2.1.1 |
| IdP `/admin` | `refresh_rotation` | off: refresh token reusable | on: rotated, reuse revokes the family | RFC 9700 §4.14.2 |
| Client `/settings` | `validate_aud` | off | on | OIDC Core 1.0 §3.1.3.7 |
| Client `/settings` | `validate_nonce` | off | on (and single use) | OIDC Core 1.0 §3.1.3.7, §15.5.2 |
| Client `/settings` | `wrong_verifier` | — | — (sends a wrong PKCE verifier, for step 3) | RFC 7636 §4.6 |

## Open it

**Codespaces:**

```bash
cd m17-identity/oidc-lab
pip install -r requirements.txt
python oidc_lab.py selftest     # 10 automated checks, a few seconds
python oidc_lab.py serve
```

In the **Ports** tab, both 9000 and 9001 appear. Keep them **Private**. Open port 9001 in the browser. In a Codespace the lab detects the `*.app.github.dev` forwarded URLs and uses them as the redirect URI and issuer.

**Colab:** open [`M17-OIDC-Lab.ipynb`](https://colab.research.google.com/github/anthonyhammock/ai-hiring-audit-lab/blob/main/m17-identity/oidc-lab/M17-OIDC-Lab.ipynb). Colab cannot show the browser pages easily, so the notebook drives the flows headlessly (`selftest`) and from Python, and prints the flow trace.

## Lesson 02 lab steps

1. Client registration with an exact redirect URI is preset (`client-a`; see IdP `/admin`). Sign in from the client's home page (**Sign in**).
2. On the client home page, read the flow trace: find `state`, `code_challenge`, `code_verifier` and `iss`.
3. In client **settings**, tick `wrong_verifier`, sign in again, and confirm the IdP rejects the code.
4. In IdP **admin**, tick `wildcard_redirects`. Edit the `redirect_uri` in the authorization URL (for example change the host to `127.0.0.1:9001.evil.example`) and watch the IdP accept it. Untick it again. (`selftest` does this headlessly.)
5. Click **Test: token for client B**: your client must reject it on `aud`. Then untick `validate_aud` and repeat.
6. Tick `refresh_rotation` in IdP admin, sign in, and click **Test: refresh reuse**.
7. Write the checklist mapping each control to its RFC or OIDC Core section (the trace's references are a starting point; verify each against the primary source).

For the assignment's "replayed nonce" check, use **Test: replay ID Token**.
