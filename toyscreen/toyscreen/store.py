"""Candidate database (component 3): SQLite with candidates, stages and scores.

Seeded with 30 FICTIONAL candidates. Contact details are fake on purpose so that
leakage (LLM02) is visible in outputs and logs.
"""
from __future__ import annotations

import os
import sqlite3

from .data import candidates

SCHEMA = """
CREATE TABLE candidates (id TEXT PRIMARY KEY, name TEXT, email TEXT, phone TEXT, resume TEXT);
CREATE TABLE stages (candidate_id TEXT PRIMARY KEY, stage TEXT);
CREATE TABLE scores (candidate_id TEXT, score INTEGER, rationale TEXT, source TEXT);
"""


def open_db(path: str) -> sqlite3.Connection:
    """Create and seed a fresh database. A file path is recreated on every call."""
    if path != ":memory:":
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        if os.path.exists(path):
            os.remove(path)
    conn = sqlite3.connect(path, check_same_thread=False)
    conn.executescript(SCHEMA)
    for c in candidates():
        conn.execute("INSERT INTO candidates VALUES (?,?,?,?,?)",
                     (c["id"], c["name"], c["email"], c["phone"], c["resume"]))
        conn.execute("INSERT INTO stages VALUES (?, 'applied')", (c["id"],))
    conn.commit()
    return conn


def get_candidate(conn: sqlite3.Connection, cid: str) -> dict | None:
    row = conn.execute("SELECT id, name, email, phone, resume FROM candidates WHERE id=?", (cid,)).fetchone()
    return dict(zip(("id", "name", "email", "phone", "resume"), row)) if row else None


def all_candidates(conn: sqlite3.Connection) -> list[dict]:
    rows = conn.execute("SELECT id, name, email, phone FROM candidates ORDER BY id").fetchall()
    return [dict(zip(("id", "name", "email", "phone"), r)) for r in rows]


def stage_of(conn: sqlite3.Connection, cid: str) -> str | None:
    row = conn.execute("SELECT stage FROM stages WHERE candidate_id=?", (cid,)).fetchone()
    return row[0] if row else None


def latest_score(conn: sqlite3.Connection, cid: str) -> int | None:
    row = conn.execute("SELECT score FROM scores WHERE candidate_id=? ORDER BY rowid DESC LIMIT 1",
                       (cid,)).fetchone()
    return row[0] if row else None


# Fixed, parameterised reports offered in hardened mode instead of model-written SQL.
FIXED_REPORTS = {
    "stage_counts": "SELECT stage, COUNT(*) FROM stages GROUP BY stage ORDER BY stage",
    "score_for_candidate": "SELECT candidate_id, score FROM scores WHERE candidate_id = ?",
}
