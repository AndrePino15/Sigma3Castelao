from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable, List

from .models import SeatMap, SeatMapEntry


def build_indexes(seat_map: SeatMap) -> SeatMap:
    """Build in-memory seat/node lookup dictionaries and validate uniqueness."""

    seat_map.by_seat_id = {}
    seat_map.by_node_id = {}
    seat_map.section_seat_ids = {}
    for seat in seat_map.seats:
        if seat.seat_id in seat_map.by_seat_id:
            raise ValueError(f"Duplicate seat_id {seat.seat_id}")
        if seat.node_id in seat_map.by_node_id:
            raise ValueError(f"Duplicate node_id {seat.node_id}")
        seat_map.by_seat_id[seat.seat_id] = seat
        seat_map.by_node_id[seat.node_id] = seat
        seat_map.section_seat_ids.setdefault(seat.section_id, []).append(seat.seat_id)
    return seat_map


def _parse_entries(entries: Iterable[dict]) -> List[SeatMapEntry]:
    """Parse raw JSON seat entries into typed SeatMapEntry objects."""

    parsed: List[SeatMapEntry] = []
    for row in entries:
        parsed.append(
            SeatMapEntry(
                seat_id=int(row["seat_id"]),
                x=float(row["x"]),
                y=float(row["y"]),
                section_id=int(row["section_id"]),
                node_id=int(row["node_id"]),
            )
        )
    return parsed


def load_section_seat_map(path: str | Path, expected_section_id: int | None = None) -> SeatMap:
    """Load and validate a section seat map from JSON on disk."""

    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    seat_map = SeatMap(
        version=str(raw.get("version", "v1")),
        canvas_width=int(raw.get("canvas_width", 0)),
        canvas_height=int(raw.get("canvas_height", 0)),
        seats=_parse_entries(raw.get("seats", [])),
    )
    build_indexes(seat_map)
    if expected_section_id is not None:
        for seat in seat_map.seats:
            if seat.section_id != expected_section_id:
                raise ValueError(
                    f"Seat {seat.seat_id} section mismatch: {seat.section_id} != {expected_section_id}"
                )
    return seat_map
