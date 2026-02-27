from __future__ import annotations

import time
import uuid
from typing import Any, Dict

from .. import messages
from ..mqtt_topics import led_topic


class CueService:
    """Builds and publishes versioned LED cue commands on existing /led topics."""

    def __init__(self, mqtt_client, show_clock=None) -> None:
        """Create a cue publisher with optional show-clock source."""

        self.mqtt_client = mqtt_client
        self.show_clock = show_clock

    def _now_show_time_ms(self) -> int:
        """Return current show time used to schedule future cue starts."""

        if self.show_clock is not None and hasattr(self.show_clock, "current_show_time_ms"):
            return int(self.show_clock.current_show_time_ms())
        return int(time.monotonic() * 1000.0)

    def publish_cue_start(
        self,
        section_id: str,
        animation_id: str,
        params: Dict[str, Any],
        *,
        duration_ms: int = 8000,
        loop: bool = False,
        cue_id: str | None = None,
        lead_ms: int = 500,
    ) -> str:
        """Publish CUE_START for one section and return cue_id."""

        cid = cue_id or str(uuid.uuid4())
        start_time_show_ms = self._now_show_time_ms() + int(lead_ms)
        msg = messages.build_led_cue_start(
            cue_id=cid,
            animation_id=animation_id,
            start_time_show_ms=start_time_show_ms,
            duration_ms=duration_ms,
            loop=loop,
            section_id=int(section_id),
            params=params,
        )
        self.mqtt_client.publish(led_topic(str(section_id)), msg)
        return cid

    def publish_cue_stop(self, section_id: str, cue_id: str) -> None:
        """Publish CUE_STOP for one section/cue pair."""

        self.mqtt_client.publish(led_topic(str(section_id)), messages.build_led_cue_stop(cue_id))
