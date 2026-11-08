"""A deliberately simple in-memory vector store (component 4).

Embeddings are TF-IDF vectors over word tokens, compared by cosine similarity. That
is enough to show retrieval weaknesses without downloading an embedding model.

Vulnerable (unlabelled_vector_store=True): résumé chunks from every candidate and
all hiring notes share one collection with no access labels, so screening candidate
A can retrieve text that candidate B planted in B's résumé.
Vulnerable (unapproved_notes=True): anyone with the "notes" role can add a note and
it is retrievable at once, with no approval and no provenance.

Hardened: every chunk carries labels (kind, candidate_id, approved, author);
retrieval filters by label, and notes wait in a queue until approved.
"""
from __future__ import annotations

import math
import re
from collections import Counter
from dataclasses import dataclass, field

TOKEN = re.compile(r"[a-z0-9]+")


def tokens(text: str) -> list[str]:
    return TOKEN.findall(text.lower())


@dataclass
class Chunk:
    id: str
    text: str
    labels: dict = field(default_factory=dict)


class VectorStore:
    def __init__(self, labelled: bool, require_approval: bool):
        self.labelled = labelled
        self.require_approval = require_approval
        self.chunks: list[Chunk] = []
        self.pending_notes: list[Chunk] = []

    # -- ingestion ---------------------------------------------------------
    def add_resume(self, cid: str, text: str) -> None:
        for i, para in enumerate(p for p in text.split("\n\n") if p.strip()):
            self.chunks.append(Chunk(f"{cid}#{i}", para, {"kind": "resume", "candidate_id": cid}))

    def add_note(self, note_id: str, text: str, author: str, approved: bool = False) -> str:
        if not self.require_approval:
            approved = True  # no approval step: every note counts as approved the moment it arrives
        chunk = Chunk(note_id, text, {"kind": "note", "author": author, "approved": approved})
        if not approved:
            self.pending_notes.append(chunk)
            return "queued for approval"
        self.chunks.append(chunk)
        return "added"

    def approve_note(self, note_id: str, approver: str) -> None:
        for ch in list(self.pending_notes):
            if ch.id == note_id:
                ch.labels.update(approved=True, approver=approver)
                self.pending_notes.remove(ch)
                self.chunks.append(ch)

    # -- retrieval ---------------------------------------------------------
    def _idf(self) -> dict[str, float]:
        df = Counter(t for ch in self.chunks for t in set(tokens(ch.text)))
        n = len(self.chunks) or 1
        return {t: math.log((1 + n) / (1 + d)) + 1 for t, d in df.items()}

    def _vec(self, text: str, idf: dict[str, float]) -> dict[str, float]:
        tf = Counter(tokens(text))
        return {t: c * idf.get(t, 1.0) for t, c in tf.items()}

    @staticmethod
    def _cos(a: dict, b: dict) -> float:
        dot = sum(v * b.get(k, 0.0) for k, v in a.items())
        na = math.sqrt(sum(v * v for v in a.values()))
        nb = math.sqrt(sum(v * v for v in b.values()))
        return dot / (na * nb) if na and nb else 0.0

    def search(self, query: str, k: int = 4, candidate_id: str | None = None) -> list[Chunk]:
        pool = self.chunks
        if self.labelled:
            pool = [ch for ch in pool
                    if (ch.labels.get("kind") == "note" and ch.labels.get("approved"))
                    or ch.labels.get("candidate_id") == candidate_id]
        idf = self._idf()
        q = self._vec(query, idf)
        ranked = sorted(pool, key=lambda ch: self._cos(q, self._vec(ch.text, idf)), reverse=True)
        return ranked[:k]
