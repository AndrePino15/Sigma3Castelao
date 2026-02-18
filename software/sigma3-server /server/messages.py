from __future__ import annotations
from typing import Dict, Any, List, Optional
from .utils import now_ms, ensure_rgb

def build_mode_command(mode: str, reason: str = "") -> Dict[str, Any]:
    mode = mode.strip().lower()
    if mode not in {"normal", "safety"}:
        raise ValueError("mode must be 'normal' or 'safety'")
    return {"type": "mode", "ts_ms": now_ms(), "payload": {"mode": mode, "reason": reason or ""}}

def build_goal_event(team: str) -> Dict[str, Any]:
    team = team.strip().lower()
    if team not in {"home", "away"}:
        raise ValueError("team must be 'home' or 'away'")
    return {"type": "goal", "ts_ms": now_ms(), "payload": {"team": team}}

def build_vote_command(
    vote_id: str,
    duration_s: int,
    options: Optional[List[str]] = None,
    one_vote_per_seat: bool = True,
    auto_close: bool = True,
) -> Dict[str, Any]:
    if not vote_id:
        raise ValueError("vote_id cannot be empty")
    duration_s = int(duration_s)
    if duration_s <= 0:
        raise ValueError("duration_s must be positive")
    options = ["yes", "no"]  # project rule
    return {
        "type": "vote",
        "ts_ms": now_ms(),
        "payload": {
            "vote_id": vote_id,
            "duration_s": duration_s,
            "options": options,
            "one_vote_per_seat": bool(one_vote_per_seat),
            "auto_close": bool(auto_close),
        },
    }

def build_animation_command(animation_id: str, duration_s: float = 0.0) -> Dict[str, Any]:
    if not animation_id:
        raise ValueError("animation_id cannot be empty")
    return {"type": "animation", "ts_ms": now_ms(), "payload": {"animation_id": animation_id, "duration_s": float(duration_s)}}

def build_led_command_mexican_wave(
    direction: str = "left_to_right",
    speed_seats_per_s: int = 12,
    width_seats: int = 3,
    hold_ms: int = 120,
    color: Optional[Dict[str, int]] = None,
    background: Optional[Dict[str, int]] = None,
) -> Dict[str, Any]:
    direction = direction.strip().lower()
    if direction not in {"left_to_right", "right_to_left"}:
        raise ValueError("direction must be left_to_right or right_to_left")
    color = ensure_rgb(color or {"r": 0, "g": 120, "b": 255})
    background = ensure_rgb(background or {"r": 0, "g": 0, "b": 0})
    return {
        "type": "led",
        "ts_ms": now_ms(),
        "payload": {
            "pattern": "mexican_wave",
            "direction": direction,
            "speed_seats_per_s": int(speed_seats_per_s),
            "width_seats": int(width_seats),
            "hold_ms": int(hold_ms),
            "color": color,
            "background": background,
        },
    }

def build_led_command_sparkle(duration_ms: int = 8000, density: float = 0.08, spark_ms: int = 120, seed: int = 42) -> Dict[str, Any]:
    return {
        "type": "led",
        "ts_ms": now_ms(),
        "payload": {"pattern": "sparkle", "duration_ms": int(duration_ms), "density": float(density), "spark_ms": int(spark_ms), "seed": int(seed)},
    }

def build_led_command_set_seat(
    section_id: str,
    row: int,
    col: int,
    color: Optional[Dict[str, int]] = None,
    duration_ms: int = 800,
) -> Dict[str, Any]:
    """Set a single seat LED (row/col) in a given section.

    This command is intended for seat-level control and for driving the Web UI preview.
    The Raspberry Pi/Node firmware can implement it later; the server already publishes it over MQTT.
    """
    if not section_id:
        raise ValueError("section_id cannot be empty")
    row = int(row)
    col = int(col)
    if row <= 0 or col <= 0:
        raise ValueError("row and col must be positive (1-indexed)")
    color = ensure_rgb(color or {"r": 255, "g": 0, "b": 0})
    duration_ms = int(duration_ms)
    if duration_ms < 0:
        raise ValueError("duration_ms must be >= 0")
    return {
        "type": "led",
        "ts_ms": now_ms(),
        "payload": {
            "pattern": "set_seat",
            "section_id": str(section_id),
            "targets": [
                {"row": row, "col": col, "rgb": color, "duration_ms": duration_ms}
            ],
        },
    }
