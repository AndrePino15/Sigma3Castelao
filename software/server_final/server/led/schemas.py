from __future__ import annotations

from typing import Any, Dict, Optional

SHOW_CLOCK_SCHEMA_V1 = "show.clock.v1"
LED_CUE_SCHEMA_V1 = "led.cue.v1"


def is_clock_sync_payload(payload: Dict[str, Any]) -> bool:
    """Return True when payload matches the show-clock schema marker."""

    return isinstance(payload, dict) and payload.get("schema") == SHOW_CLOCK_SCHEMA_V1


def is_led_cue_payload(payload: Dict[str, Any]) -> bool:
    """Return True when payload matches the LED cue schema marker."""

    return isinstance(payload, dict) and payload.get("schema") == LED_CUE_SCHEMA_V1


def validate_cue_start_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Validate required fields for a cue-start command payload."""

    required = ["cue_id", "animation_id", "start_time_show_ms", "scope", "params"]
    missing = [k for k in required if k not in payload]
    if missing:
        raise ValueError(f"Missing cue fields: {', '.join(missing)}")
    return payload
