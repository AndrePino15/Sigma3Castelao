from __future__ import annotations

import math
from typing import Any, Dict, Tuple


class TravelingWaveAnimation:
    """Directional sine-wave animation based on seat coordinates and time."""

    def render(self, x: float, y: float, t_ms: int, params: Dict[str, Any]) -> Tuple[int, int, int]:
        """Render one RGB sample of the traveling-wave pattern."""

        dx = float(params.get("dx", 1.0))
        dy = float(params.get("dy", 0.0))
        speed = float(params.get("speed_units_per_s", 8.0))
        wavelength = float(params.get("wavelength", 8.0))
        palette = params.get("palette") or [[0, 0, 0], [0, 120, 255]]
        c0 = [int(v) for v in palette[0]]
        c1 = [int(v) for v in palette[min(1, len(palette) - 1)]]
        phase = ((x * dx) + (y * dy) - speed * (t_ms / 1000.0)) / max(wavelength, 1e-6)
        mix = 0.5 + 0.5 * math.sin(2.0 * math.pi * phase)
        return (
            int(c0[0] + (c1[0] - c0[0]) * mix),
            int(c0[1] + (c1[1] - c0[1]) * mix),
            int(c0[2] + (c1[2] - c0[2]) * mix),
        )
