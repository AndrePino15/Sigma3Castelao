"""Small helper utilities used across the server."""

from __future__ import annotations
import time
from typing import Any, Dict


def now_ms() -> int:
    """Unix time in milliseconds."""
    return int(time.time() * 1000)


def clamp_int(v: int, lo: int, hi: int) -> int:
    return max(lo, min(hi, int(v)))


def ensure_rgb(d: Dict[str, Any]) -> Dict[str, int]:
    """Validate/normalise a dict like {'r':0,'g':120,'b':255}."""
    r = clamp_int(d.get("r", 0), 0, 255)
    g = clamp_int(d.get("g", 0), 0, 255)
    b = clamp_int(d.get("b", 0), 0, 255)
    return {"r": r, "g": g, "b": b}
