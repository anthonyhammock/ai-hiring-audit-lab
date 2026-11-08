"""Recruiter view (component 8): an HTML page built from model output.

Vulnerable (raw_html_output=True): the rationale goes into the page unencoded and
Markdown images become <img> tags, so a browser opening the page would fetch an
attacker-chosen URL (LLM05). Hardened: HTML-escaped output, a strict Content
Security Policy, and images shown as inert text.

The page is written to a file for you to inspect. Open it only inside your Codespace
or notebook; image URLs in the samples use reserved example.org domains.
"""
from __future__ import annotations

import html
import re

MD_IMAGE = re.compile(r"!\[([^\]]*)\]\(([^)]*)\)")
CSP = "default-src 'none'; style-src 'unsafe-inline'; img-src 'none'"


def recruiter_view(rows: list[dict], raw_html_output: bool) -> str:
    out = ["<!doctype html><html><head><meta charset='utf-8'>"]
    if not raw_html_output:
        out.append(f"<meta http-equiv='Content-Security-Policy' content=\"{CSP}\">")
    out.append("<title>ToyScreen recruiter view (FICTIONAL)</title></head><body>")
    out.append("<h1>ToyScreen recruiter view</h1><p>FICTIONAL training data.</p><table border=1>")
    out.append("<tr><th>Candidate</th><th>Score</th><th>Rationale</th><th>Review</th></tr>")
    for r in rows:
        rationale = r.get("rationale", "")
        if raw_html_output:
            rationale = MD_IMAGE.sub(lambda m: f"<img alt='{m.group(1)}' src='{m.group(2)}'>", rationale)
        else:
            rationale = MD_IMAGE.sub(lambda m: f"[image not loaded: {m.group(2)}]", html.escape(rationale))
        out.append(f"<tr><td>{html.escape(r['candidate_id'])}</td><td>{r.get('score')}</td>"
                   f"<td>{rationale}</td><td>{'NEEDS HUMAN REVIEW' if r.get('needs_review') else ''}</td></tr>")
    out.append("</table></body></html>")
    return "\n".join(out)
