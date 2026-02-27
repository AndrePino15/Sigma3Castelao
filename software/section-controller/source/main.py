from __future__ import annotations

import logging
import signal
import threading
import os

from app import Bridge
from audio import AudioConfig, AudioService

LOGGER = logging.getLogger(__name__)

def main() -> int:
    """Run the full controller stack (audio + MQTT + CAN)."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    )

    raw_section_id = os.getenv("SC_ID")
    if raw_section_id is None or raw_section_id.strip() == "":
        LOGGER.error("Missing required environment variable SC_ID")
        return 2
    try:
        section_id = int(raw_section_id)
    except ValueError:
        LOGGER.error("Invalid SC_ID=%r (expected integer)", raw_section_id)
        return 2

    broker_host = os.getenv("SC_BROKER_HOST", "172.20.10.5").strip() or "172.20.10.5"
    broker_port_raw = os.getenv("SC_BROKER_PORT", "1883").strip() or "1883"
    try:
        broker_port = int(broker_port_raw)
    except ValueError:
        LOGGER.error("Invalid SC_BROKER_PORT=%r (expected integer)", broker_port_raw)
        return 2

    can_channel = os.getenv("SC_CAN_CHANNEL", "can0").strip() or "can0"
    can_interface = os.getenv("SC_CAN_INTERFACE", "socketcan").strip() or "socketcan"

    audio_config = AudioConfig.from_env()
    LOGGER.info(
        "Startup config: section_id=%s broker=%s:%s can=%s/%s audio_enable=%s audio_autostart=%s",
        section_id,
        broker_host,
        broker_port,
        can_channel,
        can_interface,
        audio_config.enable,
        audio_config.autostart,
    )

    controller = Bridge(
        section_id=section_id,
        broker_host=broker_host,
        broker_port=broker_port,
        can_channel=can_channel,
        can_interface=can_interface,
    )

    audio_service = AudioService(audio_config, logger=logging.getLogger("audio.service"))

    # creation of shutdown_event flag to control which is used as a shutdown check in all audio modules
    shutdown_event = threading.Event()

    def _handle_shutdown(signum: int, _frame: object) -> None:
        LOGGER.info("Received signal %s, shutting down services", signum)
        shutdown_event.set()
        # Request the bridge loop to exit; actual transport teardown stays in finally
        # to avoid races where controller.stop() nulls transport objects mid-iteration.
        controller.request_stop()

    signal.signal(signal.SIGINT, _handle_shutdown)
    if hasattr(signal, "SIGTERM"):
        signal.signal(signal.SIGTERM, _handle_shutdown)

    try:
        if audio_config.enable and audio_config.autostart:
            LOGGER.info("Starting audio service")
            try:
                audio_service.start()
            except Exception:
                LOGGER.exception("Audio service failed to start")
                raise
        else:
            LOGGER.info("Audio service disabled or autostart off; skipping audio startup")

        LOGGER.info("Starting bridge (MQTT + CAN)")
        try:
            controller.start()
        except Exception:
            LOGGER.exception("Bridge startup failed")
            raise

        LOGGER.info("Entering bridge run loop")
        try:
            controller.run()
        except Exception:
            LOGGER.exception("Bridge run loop failed")
            raise
    finally:
        shutdown_event.set()
        controller.stop()
        audio_service.stop()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

