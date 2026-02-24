from __future__ import annotations

import logging
import signal
import threading

from app.bridge import Bridge
from audio import AudioConfig, AudioService

LOGGER = logging.getLogger(__name__)


def main() -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    )

    """ ip_address = "172.20.10.4"
    controller = Bridge(
        section_id=12345,
        broker_host=ip_address,
        broker_port=1883,
        can_channel="can0",
        can_bustype="socketcan",
    ) """

    audio_config = AudioConfig.from_env()
    audio_service = AudioService(audio_config, logger=logging.getLogger("audio.service"))

    shutdown_event = threading.Event()

    def _handle_shutdown(signum: int, _frame: object) -> None:
        LOGGER.info("Received signal %s, shutting down services", signum)
        shutdown_event.set()
        # controller.stop()
        audio_service.stop()

    signal.signal(signal.SIGINT, _handle_shutdown)
    if hasattr(signal, "SIGTERM"):
        signal.signal(signal.SIGTERM, _handle_shutdown)

    # Manual smoke check:
    # From repo root: export SC_AUDIO_ENABLE=1; export SC_AUDIO_AUTOSTART=1; python3 source/main.py
    # From source/:   export SC_AUDIO_ENABLE=1; export SC_AUDIO_AUTOSTART=1; python3 main.py
    # Expect: audio runner subprocess starts, and Ctrl+C / SIGTERM stops it cleanly.
    try:
        if audio_config.enable and audio_config.autostart:
            audio_service.start()

        #controller.start()
        #controller.run()
    finally:
        shutdown_event.set()
        #controller.stop()
        audio_service.stop()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

