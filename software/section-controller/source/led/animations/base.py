from __future__ import annotations

from typing import Any, Dict, Protocol, Tuple


class AnimationProtocol(Protocol):
    """Common interface for deterministic parametric LED animations."""

    def render(self, x: float, y: float, t_ms: int, params: Dict[str, Any]) -> Tuple[int, int, int]:
        """Return an RGB tuple for one sample point and show time."""

        ...
