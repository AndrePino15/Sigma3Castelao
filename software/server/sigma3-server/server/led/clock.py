from __future__ import annotations

import threading
import time
from typing import Optional

from .. import messages
from ..mqtt_topics import show_clock_topic


class ShowClockPublisher:
    """
    Publisher for periodic CLOCK_SYNC messages.

    The server owns one instance and keeps it running in a background thread.
    """

    def __init__(self, mqtt_client, period_ms: int = 1000) -> None:
        """Create a periodic show-clock publisher bound to an MQTT client."""

        self.mqtt_client = mqtt_client
        self.period_ms = int(period_ms)
        self._seq = 0
        self._start_monotonic = time.monotonic()
        self._thread: Optional[threading.Thread] = None
        self._stop = threading.Event()

    def current_show_time_ms(self) -> int:
        """Return elapsed show time from local monotonic clock."""

        return int((time.monotonic() - self._start_monotonic) * 1000.0)

    def publish_once(self) -> None:
        """Publish one CLOCK_SYNC message immediately."""

        self._seq += 1
        msg = messages.build_clock_sync(self._seq, self.current_show_time_ms())
        self.mqtt_client.publish(show_clock_topic(), msg)

    def start(self) -> None:
        """Start background periodic clock publishing."""

        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._loop, name="show-clock", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        """Stop background clock publishing thread."""

        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=1.0)

    def _loop(self) -> None:
        """Background loop that publishes clock sync messages at fixed period."""

        while not self._stop.is_set():
            self.publish_once()
            self._stop.wait(self.period_ms / 1000.0)
