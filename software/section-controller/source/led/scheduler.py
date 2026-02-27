from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Dict, Optional

import can

import canbus.protocol as protocol
from .models import Rgb, SeatMap


@dataclass
class SchedulerStats:
    """Counters and latest timing for scheduler telemetry."""
    sent_frames: int = 0
    last_tick_show_time_ms: Optional[int] = None


class FixedRateCanScheduler:
    """Fixed 10 Hz scheduler; always sends LED frames (no delta suppression)."""
    def __init__(
        self,
        seat_map: Optional[SeatMap] = None,
        send_can: Optional[Callable[[can.Message], None]] = None,
        vote_request_for_node: Optional[Callable[[int], bool]] = None,
        reply_request_for_node: Optional[Callable[[int], bool]] = None,
        on_tick_start: Optional[Callable[[int], None]] = None,
    ) -> None:
        """Initialize scheduler dependencies and optional vote/reply callbacks."""
        self.seat_map = seat_map
        self.send_can = send_can
        self.vote_request_for_node = vote_request_for_node or (lambda _node_id: False)
        self.reply_request_for_node = reply_request_for_node or (lambda _node_id: False)
        self.on_tick_start = on_tick_start
        self.stats = SchedulerStats()

    def tick(self, colors_t: Dict[int, Rgb], colors_t_plus_50ms: Dict[int, Rgb], show_time_ms: int) -> int:
        """Send one 10 Hz sweep using two 20 Hz subframes per seat/node."""
        if self.seat_map is None or self.send_can is None:
            return 0
        if self.on_tick_start is not None:
            self.on_tick_start(int(show_time_ms))
        sent = 0
        for seat in self.seat_map.seats:
            c1 = colors_t.get(seat.seat_id, (0, 0, 0))
            c2 = colors_t_plus_50ms.get(seat.seat_id, c1)
            msg = protocol.encode_node_frame(
                seat.node_id,
                c1,
                c2,
                vote_request=self.vote_request_for_node(seat.node_id),
                reply_request=self.reply_request_for_node(seat.node_id),
            )
            self.send_can(msg)
            sent += 1
        self.stats.sent_frames += sent
        self.stats.last_tick_show_time_ms = int(show_time_ms)
        return sent
