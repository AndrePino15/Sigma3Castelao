from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass
class ClockSample:
    """One accepted clock-sync sample and its derived local offset."""

    seq: int
    seq: int
    show_time_ms: int
    local_monotonic_ms: float
    offset_ms: float


class ShowClockEstimator:
    """Maintains a smoothed show-time offset from periodic CLOCK_SYNC messages."""
    def __init__(self, alpha: float = 0.2, outlier_threshold_ms: float = 250.0) -> None:
        '''
        Constructor for clock synchronasiation and show clock estimation. Just sets initial values for constants.
        '''
        # alpha is the smoothing constant
        self.alpha = float(alpha)
        self.outlier_threshold_ms = float(outlier_threshold_ms)
        self._offset_ms: Optional[float] = None

    def update_from_clock_sync(self, payload: dict, local_monotonic_s: float) -> Optional[ClockSample]:
        '''
        Update clock from the show.clocl.v1 json schema published by server on topic safegoals/show/clock
        and consume the message, applying smoothing to the offset.
        '''
        # make sure we are workng with correct json schema
        inner = payload.get("payload") if isinstance(payload.get("payload"), dict) else payload
        if not isinstance(inner, dict) or inner.get("schema") != "show.clock.v1":
            return None
        if "show_time_ms" not in inner:
            return None
        # update the show_time_ms variable from the published show.clock.v1 json
        show_time_ms = int(inner["show_time_ms"])
        local_ms = float(local_monotonic_s) * 1000.0
        # measure the oofset in between the show time and the local time
        measured_offset = show_time_ms - local_ms
        # logic to assign the _offset_ms value
        if self._offset_ms is None:
            self._offset_ms = measured_offset
        elif abs(measured_offset - self._offset_ms) <= self.outlier_threshold_ms:
            # applies smoothing to offset
            self._offset_ms = self.alpha * measured_offset + (1.0 - self.alpha) * self._offset_ms
        return ClockSample(
            seq=int(inner.get("seq", -1)),
            show_time_ms=show_time_ms,
            local_monotonic_ms=local_ms,
            offset_ms=float(self._offset_ms if self._offset_ms is not None else 0.0),
        )

    def show_time_ms(self, local_monotonic_s: float) -> int:
        '''Accessor method for theshow_time_ms variable'''
        local_ms = float(local_monotonic_s) * 1000.0
        return int(local_ms + (self._offset_ms or 0.0))

    def offset_ms(self) -> Optional[float]:
        '''Accessor method for the _offset_ms variable'''
        return self._offset_ms

