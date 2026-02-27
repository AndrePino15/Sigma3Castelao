from __future__ import annotations

from typing import Dict, Optional

from .animations import get_animation
from .cue_store import CueStore
from .models import Cue, Rgb, SeatMap
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
            return self._render_active_cue(active[0], show_time_ms)
        return self._render_fallback(show_time_ms)

    def _render_active_cue(self, cue: Cue, show_time_ms: int) -> Dict[int, Rgb]:
        """Render the highest-priority active cue."""
        animation = get_animation(cue.animation_id)
        if self.render_mode == "pixel" and self.visual_pixel_map is not None and self.visual_pixel_map.pixels:
            pixel_colors: Dict[int, Rgb] = {}
            for pixel in self.visual_pixel_map.pixels:
                params = dict(cue.params)
                params["pixel_id"] = pixel.pixel_id
                pixel_colors[pixel.pixel_id] = animation.render(pixel.x, pixel.y, show_time_ms, params)
            return self.visual_pixel_map.expand_pixel_colors(pixel_colors)
        return {
            seat.seat_id: animation.render(seat.x, seat.y, show_time_ms, cue.params)
            for seat in self.seat_map.seats
        }

    def _render_fallback(self, show_time_ms: int) -> Dict[int, Rgb]:
        """Render fallback sparkle when no cues are active."""
        fallback = get_animation("sparkle")
        return {
            seat.seat_id: fallback.render(
                seat.x,
                seat.y,
                show_time_ms,
                {"seat_id": seat.seat_id, "seed": 1, "density": 0.02, "base_rgb": [0, 0, 8], "spark_rgb": [0, 30, 80]},
            )
            for seat in self.seat_map.seats
        }
