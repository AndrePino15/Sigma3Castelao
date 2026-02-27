from __future__ import annotations

from typing import Any, Dict, List


def cue_to_preview_event(sections: List[str], cue_payload: Dict[str, Any]) -> Dict[str, Any]:
    """Translate a cue payload into the existing browser preview-event shape."""

    return {
        "kind": "led",
        "pattern": cue_payload.get("animation_id", "cue"),
        "sections": sections,
        "params": cue_payload.get("params", {}),
        "cue": {
            "cue_id": cue_payload.get("cue_id"),
            "start_time_show_ms": cue_payload.get("start_time_show_ms"),
            "duration_ms": cue_payload.get("duration_ms"),
            "loop": cue_payload.get("loop"),
        },
    }
