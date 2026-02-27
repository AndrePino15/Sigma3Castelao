from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

Rgb = Tuple[int, int, int]


@dataclass(frozen=True)
class SeatMapEntry:
    """One physical seat mapping entry used by the local renderer/scheduler."""
    seat_id: int
    x: float
    y: float
    section_id: int
    node_id: int


@dataclass
class SeatMap:
    """Container for seat entries plus lookup indexes used at runtime."""
    version: str
    canvas_width: int
    canvas_height: int
    seats: List[SeatMapEntry]
    # i am using field(default_factory=dict) because as this is a @dataclass method this makes sure every new instance 
    # of the class gets an empty container
    by_seat_id: Dict[int, SeatMapEntry] = field(default_factory=dict)
    by_node_id: Dict[int, SeatMapEntry] = field(default_factory=dict)
    section_seat_ids: Dict[int, List[int]] = field(default_factory=dict)


@dataclass(frozen=True)
class Cue:
    """A time-based animation command resolved locally by the section controller."""
    cue_id: str
    animation_id: str
    start_time_show_ms: int
    duration_ms: Optional[int]
    loop: bool
    scope: Dict[str, Any]
    params: Dict[str, Any]
    priority: int = 100


@dataclass
class ActiveCueState:
    """Tracks lifecycle state for a cue in the local cue store."""
    cue: Cue
    state: str = "scheduled"


@dataclass
class SectionLedStatus:
    """Small LED runtime telemetry snapshot for status publishing."""
    engine: str = "idle"
    active_cue_ids: List[str] = field(default_factory=list)
    show_time_ms: Optional[int] = None
    offset_ms: Optional[float] = None
    render_mode: str = "seat"
    notes: List[str] = field(default_factory=list)

