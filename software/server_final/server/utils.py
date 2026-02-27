import time
from typing import List

def now_ms() -> int:
    return int(time.time() * 1000)

def parse_sections(raw: str) -> List[str]:
    """Parse 'A,B,C' -> ['A','B','C'] with cleanup."""
    if not raw:
        return []
    parts = [p.strip() for p in raw.split(",")]
    parts = [p for p in parts if p]
    return parts
