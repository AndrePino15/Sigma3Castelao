from __future__ import annotations
import threading
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

@dataclass
class SectionStatus:
    section_id: str
    last_ts: int = 0
    occupancy: int = 0
    votes: Dict[str, Any] = field(default_factory=dict)
    heartbeat: bool = False
    alerts: List[str] = field(default_factory=list)

_lock = threading.Lock()
_sections: Dict[str, SectionStatus] = {}

def update_from_telemetry(payload: Dict[str, Any]) -> None:
    section_id = str(payload.get("section_id", "")).strip()
    if not section_id:
        return
    with _lock:
        s = _sections.get(section_id) or SectionStatus(section_id=section_id)
        s.last_ts = int(payload.get("ts_ms", s.last_ts) or s.last_ts)
        s.occupancy = int(payload.get("occupancy", s.occupancy) or s.occupancy)
        s.votes = payload.get("votes", s.votes) or s.votes
        s.heartbeat = bool(payload.get("heartbeat", True))
        s.alerts = list(payload.get("alerts", s.alerts) or s.alerts)
        _sections[section_id] = s

def get_all_sections() -> List[SectionStatus]:
    with _lock:
        return list(_sections.values())

# Preview state (latest LED command)
_preview_lock = threading.Lock()
_preview_led_command: Optional[Dict[str, Any]] = None

def set_preview_led_command(cmd: Dict[str, Any]) -> None:
    global _preview_led_command
    with _preview_lock:
        _preview_led_command = cmd

def get_preview_led_command() -> Optional[Dict[str, Any]]:
    with _preview_lock:
        return _preview_led_command
