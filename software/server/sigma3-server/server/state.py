"""In-memory telemetry state store.

Why in-memory?
- Simple for a coursework prototype.
- Fast and easy to debug.

If you later need persistence:
- Replace this with SQLite/Redis/PostgreSQL.

Thread safety:
- MQTT callbacks run in a background thread.
- Flask runs in the main thread.
- So we guard shared state with a lock.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from typing import Any, Dict, List


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
    """Update section status from a telemetry JSON dict."""
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
    """Return a snapshot list of all sections."""
    with _lock:
        return list(_sections.values())
