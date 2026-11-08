"""Upload handling and text extraction (component 2).

Vulnerable (pass_hidden_text=True): every character pypdf can find goes straight to
the model, including white-on-white text, 1-point text, text placed outside the
page and text drawn in invisible render mode 3.

Hardened: walk the page's content stream, keep only text a human reader would see,
flag the document for human review if anything was hidden, normalise Unicode (NFKC)
and strip zero-width/control characters. Length caps live in pipeline.py.
"""
from __future__ import annotations

import io
import re
import unicodedata
from dataclasses import dataclass, field

from pypdf import PdfReader
from pypdf.generic import ContentStream

ZERO_WIDTH = re.compile("[​-‏‪-‮⁠-⁤﻿]")


@dataclass
class Extraction:
    text: str
    hidden_segments: list[dict] = field(default_factory=list)
    needs_review: bool = False


def normalise(text: str) -> str:
    text = unicodedata.normalize("NFKC", text)
    text = ZERO_WIDTH.sub("", text)
    return "".join(ch for ch in text if ch in "\n\t" or unicodedata.category(ch)[0] != "C")


def _decode(obj) -> str:
    if isinstance(obj, bytes):
        return obj.decode("latin-1")
    return str(obj)


def _walk_page(page) -> list[dict]:
    """Return text runs with the visual state they were drawn in."""
    x0, y0, x1, y1 = (float(v) for v in page.mediabox)
    contents = page.get_contents()
    if contents is None:
        return []
    ops = ContentStream(contents, page.pdf).operations
    runs, size, fill, mode, x, y = [], 12.0, (0.0, 0.0, 0.0), 0, 0.0, 0.0
    for operands, op in ops:
        op = op.decode() if isinstance(op, bytes) else op
        if op == "BT":
            x = y = 0.0
        elif op == "Tf":
            size = float(operands[1])
        elif op == "Tr":
            mode = int(operands[0])
        elif op == "rg":
            fill = tuple(float(v) for v in operands)
        elif op == "g":
            fill = (float(operands[0]),) * 3
        elif op == "Tm":
            x, y = float(operands[4]), float(operands[5])
        elif op in ("Td", "TD"):
            x, y = x + float(operands[0]), y + float(operands[1])
        elif op in ("Tj", "'", '"'):
            runs.append(dict(text=_decode(operands[-1]), size=size, fill=fill, mode=mode, x=x, y=y))
        elif op == "TJ":
            runs.append(dict(text="".join(_decode(o) for o in operands[0] if not isinstance(o, (int, float))),
                             size=size, fill=fill, mode=mode, x=x, y=y))
    for r in runs:
        reasons = []
        if r["mode"] == 3:
            reasons.append("invisible render mode")
        if min(r["fill"]) > 0.95:
            reasons.append("white text")
        if r["size"] < 3:
            reasons.append("font smaller than 3pt")
        if not (x0 <= r["x"] <= x1 and y0 <= r["y"] <= y1):
            reasons.append("outside the page")
        r["hidden_reasons"] = reasons
    return runs


def extract_pdf(data: bytes, pass_hidden_text: bool) -> Extraction:
    reader = PdfReader(io.BytesIO(data))
    if pass_hidden_text:
        return Extraction(text="\n".join(p.extract_text() or "" for p in reader.pages))
    visible, hidden = [], []
    for n, page in enumerate(reader.pages):
        for r in _walk_page(page):
            if r["hidden_reasons"]:
                hidden.append(dict(page=n + 1, text=r["text"], reasons=r["hidden_reasons"]))
            else:
                visible.append(r["text"])
    return Extraction(text=normalise("\n".join(visible)), hidden_segments=hidden, needs_review=bool(hidden))


def extract_docx(data: bytes, pass_hidden_text: bool) -> Extraction:
    import docx  # python-docx

    d = docx.Document(io.BytesIO(data))
    visible, hidden = [], []
    for para in d.paragraphs:
        for run in para.runs:
            is_hidden = bool(run.font.hidden) or (run.font.size is not None and run.font.size.pt < 3)
            color = run.font.color.rgb if run.font.color is not None and run.font.color.type else None
            if color is not None and str(color).upper() == "FFFFFF":
                is_hidden = True
            (hidden if is_hidden else visible).append(run.text)
        visible.append("\n")
    if pass_hidden_text:
        return Extraction(text="\n".join(p.text for p in d.paragraphs))
    return Extraction(text=normalise("".join(visible)),
                      hidden_segments=[dict(text=t, reasons=["hidden or white run"]) for t in hidden],
                      needs_review=bool(hidden))


def extract(filename: str, data: bytes, pass_hidden_text: bool) -> Extraction:
    if filename.lower().endswith(".pdf"):
        return extract_pdf(data, pass_hidden_text)
    if filename.lower().endswith(".docx"):
        return extract_docx(data, pass_hidden_text)
    text = data.decode("utf-8", errors="replace")
    return Extraction(text=text if pass_hidden_text else normalise(text))
