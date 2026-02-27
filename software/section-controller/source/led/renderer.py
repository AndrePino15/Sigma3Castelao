from __future__ import annotations

from typing import Dict, Optional

from .animations import get_animation
from .cue_store import CueStore
from .models import Rgb, SeatMap
from .visual_pixel_map import VisualPixelMap


class LedRenderer:
    """Renders seat colors from active cues and fallback behavior."""

    def __init__(self, seat_map: Optional[SeatMap] = None, visual_pixel_map: Optional[VisualPixelMap] = None) -> None:
        """Create a renderer with optional seat and visual-pixel maps."""

        self.seat_map = seat_map
        self.visual_pixel_map = visual_pixel_map
        self.render_mode = "seat"

    def render_frame(self, cue_store: CueStore, show_time_ms: int) -> Dict[int, Rgb]:
        """Render one frame of seat colors for the given show time."""

        if self.seat_map is None:
            return {}
        active = cue_store.active_cues(show_time_ms)
        if active:
            cue = active[0]
            anim = get_animation(cue.animation_id)
            return {
                s.seat_id: anim.render(s.x, s.y, show_time_ms, cue.params)
                for s in self.seat_map.seats
            }
        fallback = get_animation("sparkle")
        return {
            s.seat_id: fallback.render(s.x, s.y, show_time_ms, {"seat_id": s.seat_id, "seed": 1, "density": 0.02})
            for s in self.seat_map.seats
        }
