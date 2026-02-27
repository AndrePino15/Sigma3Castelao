from __future__ import annotations

from typing import Any, Dict, Tuple


def _hash32(v: int) -> int:
    """Fast deterministic 32-bit hash used for sparkle randomness."""
    v &= 0xFFFFFFFF
    v ^= (v >> 16)
    v = (v * 0x7FEB352D) & 0xFFFFFFFF
    v ^= (v >> 15)
    v = (v * 0x846CA68B) & 0xFFFFFFFF
    v ^= (v >> 16)
    return v


class SparkleAnimation:
    """Seeded deterministic sparkle animation."""
    
    def render(self, x: float, y: float, t_ms: int, params: Dict[str, Any]) -> Tuple[int, int, int]:
        """Render one RGB sample of the sparkle pattern."""
        seed = int(params.get("seed", 1))
        seat_id = int(params.get("seat_id", int(x * 1000) ^ int(y * 1000)))
        density = float(params.get("density", 0.05))
        base_rgb = params.get("base_rgb") or [0, 0, 8]
        spark_rgb = params.get("spark_rgb") or [0, 80, 200]
        tick = int(t_ms // 50)
        h = _hash32(seed ^ seat_id ^ (tick * 2654435761))
        src = spark_rgb if (h / 0xFFFFFFFF) < density else base_rgb
        return int(src[0]), int(src[1]), int(src[2])
