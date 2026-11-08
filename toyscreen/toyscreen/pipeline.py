"""Orchestrator, agent loop, scoring, limits and logging (components 6, 9, 10).

    from toyscreen import ToyScreen, load_settings
    app = ToyScreen(load_settings("vulnerable"))
    result = app.screen_file("samples/resumes/attack/attack_tiny_font__C-018.pdf", "C-018")

Scoring. llm_score_is_final=True: the model's 1-5 score is stored as final (LLM09).
False: the model only extracts fields with quotes; code checks each quote appears in
the visible résumé text and mentions the skill, computes the score from the rubric,
and marks the decision as awaiting recruiter confirmation.

Limits. no_resource_limits=True: no caps on upload size, résumé length, requests,
output tokens or agent steps (LLM10). A hard ceiling of 500 steps stops a runaway
loop from hanging your Codespace; it is not a defence.
"""
from __future__ import annotations

import json
import os
import time
from collections import Counter

from . import store
from .config import Settings
from .data import JOB, NOTES, ground_truth_score
from .extractor import extract
from .llm import make_llm, parse_json
from .prompt import chat_prompt, screening_prompt
from .render import recruiter_view
from .tools import ToolBox
from .vectorstore import VectorStore

RUNAWAY_CEILING = 500
SKILL_WORDS = {"sql": "sql", "python": "python", "tableau": "tableau",
               "survey_design": "survey", "hris": "hris"}


class LimitExceeded(Exception):
    pass


class ToyScreen:
    def __init__(self, settings: Settings, llm=None):
        self.s = settings
        self.flags = settings.flags
        self.llm = llm or make_llm(settings.backend, pinned=not self.flags.unpinned_model, seed=settings.seed)
        self.reset()

    def reset(self) -> None:
        self.conn = store.open_db(self.s.db_path)
        self.tools = ToolBox(self.conn, self.flags)
        self.vs = VectorStore(labelled=not self.flags.unlabelled_vector_store,
                              require_approval=not self.flags.unapproved_notes)
        for c in store.all_candidates(self.conn):
            self.vs.add_resume(c["id"], store.get_candidate(self.conn, c["id"])["resume"])
        for nid, text, _ in NOTES:
            self.vs.add_note(nid, text, author="hiring-lead", approved=True)
        self.requests: Counter = Counter()
        self.rows: list[dict] = []

    @property
    def outbox(self) -> list[dict]:
        return self.tools.outbox

    # -- logging -------------------------------------------------------------
    def _log(self, record: dict) -> None:
        if not self.s.log_path:
            return
        os.makedirs(os.path.dirname(self.s.log_path) or ".", exist_ok=True)
        record = {"time": time.time(), "flags": vars(self.flags), "backend": self.llm.name, **record}
        with open(self.s.log_path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, default=str) + "\n")

    def _quota(self, user: str) -> None:
        self.requests[user] += 1
        if not self.flags.no_resource_limits and self.requests[user] > self.s.max_requests_per_user:
            raise LimitExceeded(f"request quota exceeded for {user}")

    # -- notes ---------------------------------------------------------------
    def add_note(self, note_id: str, text: str, author: str = "notes-user") -> str:
        status = self.vs.add_note(note_id, text, author=author)
        self._log({"event": "add_note", "note_id": note_id, "author": author, "status": status})
        return status

    # -- screening -------------------------------------------------------------
    def screen_file(self, path: str, candidate_id: str, user: str = "recruiter") -> dict:
        with open(path, "rb") as fh:
            return self.screen(os.path.basename(path), fh.read(), candidate_id, user)

    def screen(self, filename: str, data: bytes, candidate_id: str, user: str = "recruiter") -> dict:
        f, s = self.flags, self.s
        self._quota(user)
        if not f.no_resource_limits and len(data) > s.max_upload_bytes:
            raise LimitExceeded("upload too large")
        ex = extract(filename, data, pass_hidden_text=f.pass_hidden_text)
        text = ex.text if f.no_resource_limits else ex.text[: s.max_resume_chars]
        self.vs.add_resume(candidate_id, text)
        retrieved = self.vs.search(JOB["text"], k=4, candidate_id=candidate_id)
        context = [ch.text for ch in retrieved if ch.labels.get("candidate_id") != candidate_id]
        messages = screening_prompt(text, context, f)
        max_tokens = None if f.no_resource_limits else s.max_output_tokens
        step_cap = RUNAWAY_CEILING if f.no_resource_limits else s.max_agent_steps

        first = parse_json(self.llm.chat(messages, max_tokens))
        calls_made, out = [], first
        while out.get("tool_calls") and len(calls_made) < step_cap:
            for call in out["tool_calls"][: step_cap - len(calls_made)]:
                res = self.tools.call(call.get("name", ""), call.get("args", {}), under_review=candidate_id)
                calls_made.append({"call": call, "result": res})
                messages = messages + [{"role": "tool", "content": json.dumps({"call": call, "result": res})}]
            out = parse_json(self.llm.chat(messages, max_tokens))

        if f.llm_score_is_final:
            score, rationale, source = first.get("score"), str(first.get("rationale", "")), "model"
            decision = "final"
        else:
            score, rationale = self._score_from_fields(first.get("fields", {}), text)
            source, decision = "code", "awaiting recruiter confirmation"
        if isinstance(score, int):
            self.conn.execute("INSERT INTO scores VALUES (?,?,?,?)", (candidate_id, score, rationale, source))
            self.conn.commit()
        row = dict(candidate_id=candidate_id, score=score, rationale=rationale, source=source,
                   decision=decision, needs_review=ex.needs_review, hidden_segments=ex.hidden_segments,
                   tool_calls=calls_made, steps=len(calls_made), retrieved=[ch.id for ch in retrieved],
                   pending_approvals=list(self.tools.pending_approvals))
        self.rows.append(row)
        self._log({"event": "screen", "user": user, "file": filename, "prompt": messages[:2], **row})
        return row

    @staticmethod
    def _score_from_fields(fields: dict, visible_text: str) -> tuple[int, str]:
        low = visible_text.lower()
        ok: dict = {}
        for key, word in SKILL_WORDS.items():
            fld = fields.get(key) or {}
            quote = str(fld.get("quote", "")).lower()
            ok[key] = bool(fld.get("value")) and quote and quote in low and word in quote
        yrs = fields.get("years") or {}
        yq = str(yrs.get("quote", "")).lower()
        years = int(yrs.get("value", 0)) if yq and yq in low and str(yrs.get("value")) in yq else 0
        skills = [k.replace("_", " ") for k, v in ok.items() if v]
        rejected = [k for k in SKILL_WORDS if (fields.get(k) or {}).get("value") and not ok[k]]
        note = f"Verified: {', '.join(skills) or 'none'}; years={years}."
        if rejected:
            note += f" Rejected unverifiable claims: {', '.join(rejected)}."
        return ground_truth_score(years, skills), note

    def recruiter_view(self) -> str:
        return recruiter_view(self.rows, raw_html_output=self.flags.raw_html_output)

    # -- recruiter chat (used by the HTTP server for Module 11) ---------------
    def chat(self, message: str, candidate_id: str = "C-001", user: str = "recruiter") -> str:
        self._quota(user)
        if not self.flags.no_resource_limits:
            message = message[: self.s.max_resume_chars]
        if self.flags.all_candidates_in_chat_context:
            rows = store.all_candidates(self.conn)
        else:
            c = store.get_candidate(self.conn, candidate_id)
            rows = [c] if c else []
        messages = chat_prompt(message, rows, self.flags, candidate_id)
        reply = self.llm.chat(messages, None if self.flags.no_resource_limits else self.s.max_output_tokens)
        self._log({"event": "chat", "user": user, "candidate_id": candidate_id, "message": message,
                   "reply": reply})
        return reply
