from __future__ import annotations

from typing import Any, Dict, Tuple


class WipeAnimation:
    """Directional wipe/gradient animation."""

    def render(self, x: float, y: float, t_ms: int, params: Dict[str, Any]) -> Tuple[int, int, int]:
        """Render one RGB sample for wipe animation (directional threshold)."""
        dx = float(params.get("dx", 1.0))
        dy = float(params.get("dy", 0.0))
        speed = float(params.get("speed_units_per_s", 5.0))
        edge_softness = max(0.01, float(params.get("edge_softness", 1.0)))
        palette = params.get("palette") or [[0, 0, 0], [0, 120, 255]]
        c0 = [int(v) for v in palette[0]]
        c1 = [int(v) for v in palette[min(1, len(palette) - 1)]]
        coord = (x * dx) + (y * dy)
        front = speed * (t_ms / 1000.0)
        # Soft ramp around front edge.
        mix = (front - coord + edge_softness) / (2.0 * edge_softness)
        if mix < 0.0:
            mix = 0.0
        elif mix > 1.0:
            mix = 1.0
        return (
            int(c0[0] + (c1[0] - c0[0]) * mix),
            int(c0[1] + (c1[1] - c0[1]) * mix),
            int(c0[2] + (c1[2] - c0[2]) * mix),
        )
