"""Attack success rate helpers (Module 08 method; Module 11 and 16 go deeper)."""
from __future__ import annotations

from math import sqrt


def wilson(x: int, n: int, z: float = 1.96) -> tuple[float, float]:
    """Wilson score interval for x successes in n trials."""
    if n == 0:
        return (0.0, 1.0)
    p = x / n
    centre = p + z * z / (2 * n)
    margin = z * sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    denom = 1 + z * z / n
    return (max(0.0, (centre - margin) / denom), min(1.0, (centre + margin) / denom))


def summarise(name: str, successes: int, n: int) -> str:
    lo, hi = wilson(successes, n)
    return f"{name}: ASR {successes}/{n} = {successes / n:.2f} (95% Wilson CI {lo:.2f}-{hi:.2f})"
