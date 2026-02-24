from __future__ import annotations

import os
import signal
import threading

from bridge_touchscreen import Bridge


if __name__ == "__main__":
    section_id = int(os.getenv("SECTION_ID", "12345"))
    broker_host = os.getenv("MQTT_HOST", "127.0.0.1").strip() or "127.0.0.1"
    broker_port = int(os.getenv("MQTT_PORT", "1883"))
    touchscreen_seat_id = os.getenv("SEAT_ID", f"S{section_id}")

    bridge = Bridge(
        section_id=section_id,
        broker_host=broker_host,
        broker_port=broker_port,
        touchscreen_seat_id=touchscreen_seat_id,
    )

    shutdown_event = threading.Event()

    def _handle_shutdown(_signum: int, _frame: object) -> None:
        shutdown_event.set()
        bridge.stop()

    signal.signal(signal.SIGINT, _handle_shutdown)
    if hasattr(signal, "SIGTERM"):
        signal.signal(signal.SIGTERM, _handle_shutdown)

    bridge.start()
    bridge.run()
