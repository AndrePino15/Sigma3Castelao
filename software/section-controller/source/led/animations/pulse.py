from __future__ import annotations

import math
from typing import Any, Dict, Tuple


class PulseAnimation:
    """Pulse/breathe animation with sinusoidal color interpolation."""

    def render(self, x: float, y: float, t_ms: int, params: Dict[str, Any]) -> Tuple[int, int, int]:
        """Render one RGB sample for pulse animation (sinusoidal blend)."""
        palette = params.get("palette") or [[0, 0, 0], [0, 120, 255]]
        c0 = [int(v) for v in palette[0]]
        c1 = [int(v) for v in palette[min(1, len(palette) - 1)]]
        speed_hz = float(params.get("speed_hz", 0.5))
        space_phase = float(params.get("space_phase", 0.0))
        phase = (2.0 * math.pi * speed_hz * (t_ms / 1000.0)) + ((x + y) * space_phase)
        mix = 0.5 + 0.5 * math.sin(phase)
        return (
            int(c0[0] + (c1[0] - c0[0]) * mix),
            int(c0[1] + (c1[1] - c0[1]) * mix),
            int(c0[2] + (c1[2] - c0[2]) * mix),
        )
