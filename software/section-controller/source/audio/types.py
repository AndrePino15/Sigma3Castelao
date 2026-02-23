"""Shared state/status types for the audio subsystem.

These types are intentionally lightweight and contain no runtime behavior.
They are used by the supervisor in ``audio.service`` to expose process health
without importing worker-specific logic.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional


class AudioState(Enum):
    """High-level service states reported by ``AudioService.status()``."""

    STOPPED = "stopped"
    STARTING = "starting"
    RUNNING_STREAM = "running_stream"
    RUNNING_FALLBACK = "running_fallback"
    DEGRADED = "degraded"
    ERROR = "error"


@dataclass
class AudioStatus:
    """Thread-safe snapshot payload describing audio worker process state.

    Instances are created and updated inside ``audio.service`` and returned to
    callers as copies. ``last_transition_ts`` uses ``time.monotonic()`` so it is
    suitable for elapsed-time calculations inside one process.
    """

    state: AudioState
    pid: Optional[int]
    restart_count: int
    last_error: Optional[str]
    last_transition_ts: float
    backoff_s: Optional[float]
