from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional


class AudioState(Enum):
    STOPPED = "stopped"
    STARTING = "starting"
    RUNNING_STREAM = "running_stream"
    RUNNING_FALLBACK = "running_fallback"
    DEGRADED = "degraded"
    ERROR = "error"


@dataclass
class AudioStatus:
    state: AudioState
    pid: Optional[int]
    restart_count: int
    last_error: Optional[str]
    last_transition_ts: float
    backoff_s: Optional[float]
