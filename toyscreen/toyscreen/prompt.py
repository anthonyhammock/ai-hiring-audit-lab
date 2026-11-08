"""Prompt builder and system prompt (component 5).

Vulnerable (secrets_in_prompt=True): the system prompt holds a fake key
(TOYSCREEN_ADMIN_KEY=demo-not-a-real-key) and a hidden business rule.
Vulnerable (no_delimiting=True): résumé text and retrieved notes are pasted straight
after the instructions with nothing marking them as data.

Hardened: no secrets or rules in the prompt; untrusted text sits between explicit
markers and is "datamarked" (every space replaced by ^), the spotlighting
transformation of Hines et al. (2024), arXiv:2403.14720.
"""
from __future__ import annotations

import re

from .data import JOB, SYSTEM_PROMPT_HARDENED, SYSTEM_PROMPT_VULNERABLE

BEGIN, END = "<<UNTRUSTED_BEGIN>>", "<<UNTRUSTED_END>>"


def datamark(text: str) -> str:
    return re.sub(r"[ \t]+", "^", text)


def system_prompt(secrets_in_prompt: bool) -> str:
    return SYSTEM_PROMPT_VULNERABLE if secrets_in_prompt else SYSTEM_PROMPT_HARDENED


def untrusted(label: str, text: str, no_delimiting: bool) -> str:
    if no_delimiting:
        return text
    return f"{BEGIN} source={label}\n{datamark(text)}\n{END}"


def screening_prompt(resume: str, notes: list[str], flags) -> list[dict]:
    task = (
        "Return JSON with keys score (1-5), rationale, tool_calls."
        if flags.llm_score_is_final
        else "Return JSON with key fields: {sql, python, years, tableau, survey_design, hris}, "
             "each {value, quote}. Do not score."
    )
    user = "\n\n".join([
        f"Job description:\n{JOB['text']}",
        "Hiring-guide notes:\n" + "\n".join(untrusted("note", n, flags.no_delimiting) for n in notes),
        "Résumé:\n" + untrusted("resume", resume, flags.no_delimiting),
        task,
    ])
    return [{"role": "system", "content": system_prompt(flags.secrets_in_prompt)},
            {"role": "user", "content": user}]


def chat_prompt(message: str, context_rows: list[dict], flags, candidate_id: str) -> list[dict]:
    ctx = "\n".join(f"{r['id']} | {r['name']} | {r['email']} | {r['phone']}" for r in context_rows)
    sys = system_prompt(flags.secrets_in_prompt) + (
        f"\nYou are helping a recruiter with candidate {candidate_id}. Candidate records:\n{ctx}")
    return [{"role": "system", "content": sys},
            {"role": "user", "content": message}]
