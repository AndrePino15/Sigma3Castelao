from __future__ import annotations

from typing import Any, Dict, Tuple


class ChaseAnimation:
    """Chase/scanner animation with a moving highlight band."""

    def render(self, x: float, y: float, t_ms: int, params: Dict[str, Any]) -> Tuple[int, int, int]:
        """Render one RGB sample for chase animation (moving highlight band)."""
        dx = float(params.get("dx", 1.0))
        dy = float(params.get("dy", 0.0))
        speed = float(params.get("speed_units_per_s", 6.0))
        band_width = max(0.1, float(params.get("band_width", 2.0)))
        period = max(1.0, float(params.get("period", 20.0)))
        base_rgb = params.get("base_rgb") or [0, 0, 0]
        head_rgb = params.get("head_rgb") or [0, 120, 255]

        coord = (x * dx) + (y * dy)
        center = (speed * (t_ms / 1000.0)) % period
        wrapped_dist = abs(((coord - center + (period / 2.0)) % period) - (period / 2.0))
        intensity = max(0.0, 1.0 - (wrapped_dist / band_width))
        return (
            int(base_rgb[0] + (head_rgb[0] - base_rgb[0]) * intensity),
            int(base_rgb[1] + (head_rgb[1] - base_rgb[1]) * intensity),
            int(base_rgb[2] + (head_rgb[2] - base_rgb[2]) * intensity),
        )
