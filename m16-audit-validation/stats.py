"""Small statistics helpers for Module 16: Wilson intervals and Cohen's kappa."""
from __future__ import annotations

import csv
import sys
from collections import Counter
from math import sqrt


def wilson(x: int, n: int, z: float = 1.96) -> tuple[float, float]:
    if n == 0:
        return (0.0, 1.0)
    p = x / n
    c, m, d = p + z * z / (2 * n), z * sqrt(p * (1 - p) / n + z * z / (4 * n * n)), 1 + z * z / n
    return max(0.0, (c - m) / d), min(1.0, (c + m) / d)


def cohen_kappa(a: list[str], b: list[str]) -> float:
    n = len(a)
    po = sum(x == y for x, y in zip(a, b)) / n
    ca, cb = Counter(a), Counter(b)
    pe = sum(ca[k] * cb[k] for k in set(a) | set(b)) / (n * n)
    return (po - pe) / (1 - pe) if pe < 1 else 1.0


if __name__ == "__main__":
    # python stats.py kappa labels.csv   (columns: transcript_id,human,auto)
    if len(sys.argv) == 3 and sys.argv[1] == "kappa":
        rows = list(csv.DictReader(open(sys.argv[2], newline="")))
        h, a = [r["human"].strip() for r in rows], [r["auto"].strip() for r in rows]
        k = cohen_kappa(h, a)
        agree = sum(x == y for x, y in zip(h, a))
        print(f"n={len(rows)} percent agreement={agree / len(rows):.2f} Cohen's kappa={k:.3f}")
        labels = sorted(set(h) | set(a))
        print("confusion (rows=human, cols=auto):", labels)
        for lh in labels:
            print(lh, [sum(1 for x, y in zip(h, a) if x == lh and y == la) for la in labels])
    else:
        sys.exit("usage: python stats.py kappa labels.csv")
