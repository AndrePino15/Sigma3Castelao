"""Message builders (single source of truth for JSON schemas).

Why this file exists:
- The Pi and the server MUST agree on message formats.
- If formats are scattered across routes, bugs happen.
- So: every outgoing message is constructed here.

All builder functions return a Python dict that is JSON serialisable.
"""

from __future__ import annotations

from typing import Dict, Any, List, Optional

from .utils import now_ms, ensure_rgb


def build_mode_command(mode: str, reason: str = "") -> Dict[str, Any]:
    """Build a normal/safety mode command."""
    mode = mode.strip().lower()
    if mode not in {"normal", "safety"}:
        raise ValueError("mode must be 'normal' or 'safety'")
    return {
        "type": "mode",
        "ts_ms": now_ms(),
        "payload": {"mode": mode, "reason": reason or ""},
    }


def build_goal_event(team: str) -> Dict[str, Any]:
    """Build a goal event for home/away."""
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
    """Build a vote command.

    Requirements you specified:
    - options: yes/no only
    - auto close (after duration)
    - one vote per seat
    """
    if not vote_id:
        raise ValueError("vote_id cannot be empty")
    duration_s = int(duration_s)
    if duration_s <= 0:
        raise ValueError("duration_s must be positive")

    options = options or ["yes", "no"]
    # Force the project rule
    options = ["yes", "no"]

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
    """Build an animation command.

    Meaning in your project:
    - Animation is stored on the Pi already.
    - Server only triggers playback by sending animation_id.
    """
    if not animation_id:
        raise ValueError("animation_id cannot be empty")
    return {
        "type": "animation",
        "ts_ms": now_ms(),
        "payload": {"animation_id": animation_id, "duration_s": float(duration_s)},
    }


def build_led_command_mexican_wave(
    direction: str = "left_to_right",
    speed_seats_per_s: int = 12,
    width_seats: int = 3,
    hold_ms: int = 120,
    color: Optional[Dict[str, int]] = None,
    background: Optional[Dict[str, int]] = None,
) -> Dict[str, Any]:
    """Build an LED Mexican wave command (pattern-level command).

    This does NOT send per-LED frames.
    It sends a high-level pattern request that the Pi/seat firmware interprets.
    """
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


def build_led_command_sparkle(
    duration_ms: int = 8000,
    density: float = 0.08,
    spark_ms: int = 120,
    seed: int = 42,
) -> Dict[str, Any]:
    """Build a random sparkle LED command."""
    return {
        "type": "led",
        "ts_ms": now_ms(),
        "payload": {
            "pattern": "sparkle",
            "duration_ms": int(duration_ms),
            "density": float(density),
            "spark_ms": int(spark_ms),
            "seed": int(seed),
        },
    }
