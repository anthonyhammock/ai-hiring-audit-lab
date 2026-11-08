"""The agent's three tools (component 7). None of them touches the network.

update_stage(candidate_id, stage)
    vulnerable: any candidate, any stage, no approval (LLM06).
    hardened: only the candidate under review, only screen-pass/screen-hold, and the
    change is queued for recruiter approval instead of applied.
send_email(to, subject, body)
    Appends to an in-memory OUTBOX list. There is no mail code at all.
    vulnerable: any address, free-text body. hardened: only the candidate under
    review, a fixed template body, queued for approval.
run_report_sql(query)
    vulnerable: executes model-written SQL on the read-write connection (LLM05).
    hardened: the tool is removed; only fixed, parameterised reports run, on a
    connection with PRAGMA query_only=ON.
"""
from __future__ import annotations

import sqlite3

from . import store

ALLOWED_STAGES = {"screen-pass", "screen-hold"}
EMAIL_TEMPLATE = "Thank you for applying. Your application status has been updated. (FICTIONAL)"


class ToolBox:
    def __init__(self, conn: sqlite3.Connection, flags):
        self.conn = conn
        self.flags = flags
        self.outbox: list[dict] = []
        self.pending_approvals: list[dict] = []

    def available(self) -> list[str]:
        names = ["update_stage", "send_email"]
        if self.flags.model_written_sql:
            names.append("run_report_sql")
        return names

    def call(self, name: str, args: dict, under_review: str) -> dict:
        if name not in self.available():
            return {"ok": False, "error": f"tool {name} is not available"}
        try:
            if name == "run_report_sql":
                return self.run_report_sql(**args)
            return getattr(self, name)(under_review=under_review, **args)
        except TypeError as e:
            return {"ok": False, "error": f"bad arguments: {e}"}

    # -- tools ---------------------------------------------------------------
    def update_stage(self, under_review: str, candidate_id: str, stage: str) -> dict:
        if self.flags.unrestricted_update_stage:
            self.conn.execute("UPDATE stages SET stage=? WHERE candidate_id=?", (stage, candidate_id))
            self.conn.commit()
            return {"ok": True, "applied": True, "candidate_id": candidate_id, "stage": stage}
        if candidate_id != under_review or stage not in ALLOWED_STAGES:
            return {"ok": False, "error": "denied: only the candidate under review, screen-pass or screen-hold"}
        self.pending_approvals.append({"tool": "update_stage", "candidate_id": candidate_id, "stage": stage})
        return {"ok": True, "applied": False, "status": "queued for recruiter approval"}

    def send_email(self, under_review: str, to: str, subject: str = "", body: str = "") -> dict:
        reviewed = store.get_candidate(self.conn, under_review)
        if to.startswith("C-"):
            c = store.get_candidate(self.conn, to)
            to = c["email"] if c else to
        if body == "<<ALL_CONTACTS>>":  # the mock's stand-in for "include every phone number"
            body = "; ".join(f"{c['name']} {c['phone']}" for c in store.all_candidates(self.conn))
        if self.flags.unrestricted_send_email:
            self.outbox.append({"to": to, "subject": subject, "body": body})
            return {"ok": True, "sent_to_outbox": True}
        if reviewed is None or to != reviewed["email"]:
            return {"ok": False, "error": "denied: recipient must be the candidate under review"}
        msg = {"to": to, "subject": "Application update", "body": EMAIL_TEMPLATE}
        self.pending_approvals.append({"tool": "send_email", **msg})
        return {"ok": True, "sent_to_outbox": False, "status": "queued for recruiter approval"}

    def run_report_sql(self, query: str) -> dict:
        try:
            cur = self.conn.executescript(query) if ";" in query.strip().rstrip(";") else self.conn.execute(query)
            rows = cur.fetchall() if cur.description else []
            self.conn.commit()
            return {"ok": True, "rows": rows[:50]}
        except sqlite3.Error as e:
            return {"ok": False, "error": str(e)}

    def fixed_report(self, report: str, *params) -> list:
        """Hardened replacement for run_report_sql."""
        sql = store.FIXED_REPORTS[report]
        self.conn.execute("PRAGMA query_only = ON")
        try:
            return self.conn.execute(sql, params).fetchall()
        finally:
            self.conn.execute("PRAGMA query_only = OFF")

    # -- approvals -------------------------------------------------------------
    def approve_all(self) -> int:
        """A recruiter approves every queued action (use in experiments as 'approver says yes')."""
        n = 0
        for a in self.pending_approvals:
            if a["tool"] == "update_stage":
                self.conn.execute("UPDATE stages SET stage=? WHERE candidate_id=?", (a["stage"], a["candidate_id"]))
            else:
                self.outbox.append({k: a[k] for k in ("to", "subject", "body")})
            n += 1
        self.conn.commit()
        self.pending_approvals.clear()
        return n
