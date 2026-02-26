"""Message builders (JSON dicts).

NOTE: Python 3.9 compatible typing is used (no `dict | None` union syntax).
"""
from typing import Dict, Any, Optional
from .utils import now_ms

def wrap(msg_type: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "type": msg_type,
        "ts_ms": now_ms(),
        "payload": payload,
    }

# -------- CONTROL --------
def build_mode(mode: str, reason: str = "") -> Dict[str, Any]:
    return wrap("mode", {"mode": mode, "reason": reason})

def build_goal(team: str) -> Dict[str, Any]:
    # team: "home" or "away"
    return wrap("goal", {"team": team})

def build_vote(vote_id: str, duration_s: int) -> Dict[str, Any]:
    return wrap("vote", {
        "vote_id": vote_id,
        "duration_s": duration_s,
        "options": ["yes", "no"],
        "one_vote_per_seat": True,
        "auto_close": True,
    })

def build_animation(animation_id: str, duration_s: float) -> Dict[str, Any]:
    return wrap("animation", {"animation_id": animation_id, "duration_s": duration_s})

def build_emergency(reason: str) -> Dict[str, Any]:
    return wrap("emergency", {"reason": reason})

# -------- LED --------
def build_led_mexican_wave(direction: str, speed_seats_per_s: int, width_seats: int, hold_ms: int, rgb: Dict[str, int]) -> Dict[str, Any]:
    return wrap("led", {
        "pattern": "mexican_wave",
        "direction": direction,
        "speed_seats_per_s": speed_seats_per_s,
        "width_seats": width_seats,
        "hold_ms": hold_ms,
        "rgb": rgb,
    })

def build_led_sparkle(duration_ms: int, density: float, rgb: Optional[Dict[str, int]] = None, seed: int = 42, spark_ms: int = 120) -> Dict[str, Any]:
    payload: Dict[str, Any] = {
        "pattern": "sparkle",
        "duration_ms": duration_ms,
        "density": density,
        "seed": seed,
        "spark_ms": spark_ms,
    }
    if rgb is not None:
        payload["rgb"] = rgb
    return wrap("led", payload)

def build_led_set_pixel(row: int, col: int, rgb: Dict[str, int], hold_ms: int = 500) -> Dict[str, Any]:
    # For future precise seat control (row/col mapping)
    return wrap("led", {
        "pattern": "set_pixel",
        "row": row,
        "col": col,
        "rgb": rgb,
        "hold_ms": hold_ms,
    })
