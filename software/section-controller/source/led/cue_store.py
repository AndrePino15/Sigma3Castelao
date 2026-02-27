from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List

from .models import Cue


@dataclass
class CueStoreSnapshot:
    """Snapshot of active and future cues at a specific show time."""
    active_cue_ids: List[str]
    scheduled_cue_ids: List[str]


class CueStore:
    """In-memory cue registry with deterministic active-cue resolution."""
    
    def __init__(self) -> None:
        """Constructor for an empty cue registry."""
        self._cues: Dict[str, Cue] = {}

    def add_or_replace(self, cue: Cue) -> None:
        """Insert or replace a cue by cue_id."""
        self._cues[cue.cue_id] = cue

    def stop(self, cue_id: str) -> None:
        """Stop/remove a cue if it exists."""
        self._cues.pop(cue_id, None)

    def active_cues(self, show_time_ms: int) -> List[Cue]:
        """Return currently active cues ordered by priority and start time."""
        out: List[Cue] = []
        for cue in self._cues.values():
            if show_time_ms < cue.start_time_show_ms:
                # if cue hasn't started yet, skip
                continue
            if cue.duration_ms is not None and not cue.loop:
                if show_time_ms >= cue.start_time_show_ms + cue.duration_ms:
                    # skip if cue has already finished
                    continue
            out.append(cue)
        out.sort(key=lambda c: (-int(c.priority), int(c.start_time_show_ms), c.cue_id))
        return out

    def snapshot(self, show_time_ms: int) -> CueStoreSnapshot:
        """Return active/scheduled cue IDs for telemetry/debug use."""

        active = self.active_cues(show_time_ms)
        scheduled = [c.cue_id for c in self._cues.values() if show_time_ms < c.start_time_show_ms]
        return CueStoreSnapshot(active_cue_ids=[c.cue_id for c in active], scheduled_cue_ids=scheduled)
