from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Tuple


@dataclass(frozen=True)
class VisualPixel:
    """A coarse visual pixel that maps one rendered color to multiple seats."""
    pixel_id: int
    x: float
    y: float
    seat_ids: Tuple[int, ...]


@dataclass
class VisualPixelMap:
    """Collection of visual pixels with expansion helpers."""
    pixels: List[VisualPixel] = field(default_factory=list)

    def expand_pixel_colors(self, pixel_colors: Dict[int, tuple[int, int, int]]) -> Dict[int, tuple[int, int, int]]:
        """
        Expand pixel-level colors to per-seat colors. This tells what colour each indiviual seat should have from the pixel
        mapping of the stadium.
        """
        seat_colors: Dict[int, tuple[int, int, int]] = {}
        for pixel in self.pixels:
            if pixel.pixel_id not in pixel_colors:
                continue
            for seat_id in pixel.seat_ids:
                seat_colors[seat_id] = pixel_colors[pixel.pixel_id]
        return seat_colors
