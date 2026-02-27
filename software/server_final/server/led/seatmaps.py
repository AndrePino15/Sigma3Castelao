from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Optional


class SeatMapRegistry:
    """Optional seat map registry loader for preview/scoping support."""

    def __init__(self) -> None:
        """Initialize an empty in-memory section seat-map registry."""

        self._maps: Dict[str, Dict[str, Any]] = {}

    def load_json(self, section_id: str, path: str | Path) -> None:
        """Load one section seat map from JSON file path."""

        self._maps[str(section_id)] = json.loads(Path(path).read_text(encoding="utf-8"))

    def get(self, section_id: str) -> Optional[Dict[str, Any]]:
        """Return a loaded seat map for the requested section id, if present."""

        return self._maps.get(str(section_id))
