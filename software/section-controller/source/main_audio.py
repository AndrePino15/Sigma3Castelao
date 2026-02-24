"""Standalone audio-only test entrypoint for the section-controller project.

Purpose:
- Start only the audio subsystem (no CAN, no MQTT, no Bridge).
- Exercise ``AudioService`` supervision and the ``audio.runner`` worker.
- Provide a safe manual test harness during audio development.

Setup (Raspberry Pi / Linux, run from repo root):
1. Install Python deps used by this project and install GStreamer runtime/plugins.
2. Ensure analogue output is configured on the Pi (if testing speaker output).
3. Export audio env vars (minimum example):
   - ``export SC_AUDIO_ENABLE=1``
   - ``export SC_AUDIO_AUTOSTART=1``
   - ``export SC_AUDIO_CODEC=opus``
   - ``export SC_AUDIO_RTP_PORT=5004``
4. Run:
   - ``python3 source/main_audio.py``

Run from ``source/`` instead:
- ``python3 main_audio.py``

Optional fallback-only worker test (direct worker invocation):
- ``python3 -m audio.runner --mode fallback``

Notes:
- ``AudioService`` starts the worker in auto mode (prefers stream, falls back to silence).
- This file intentionally does not import or start CAN/MQTT application components.
"""

from __future__ import annotations

import logging
import signal
import threading
import time

from audio import AudioConfig, AudioService

LOGGER = logging.getLogger(__name__)


def main() -> int:
    """Run the audio subsystem in isolation for manual testing."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    )

    config = AudioConfig.from_env()
    audio_service = AudioService(config, logger=logging.getLogger("audio.service"))
    shutdown_event = threading.Event()

    def _handle_shutdown(signum: int, _frame: object) -> None:
        """Stop the audio service on SIGINT/SIGTERM."""
        LOGGER.info("Received signal %s, shutting down audio-only test", signum)
        shutdown_event.set()
        audio_service.stop()

    signal.signal(signal.SIGINT, _handle_shutdown)
    if hasattr(signal, "SIGTERM"):
        signal.signal(signal.SIGTERM, _handle_shutdown)

    try:
        if config.enable and config.autostart:
            LOGGER.info("Starting AudioService (auto mode worker)")
            audio_service.start()
        else:
            LOGGER.info(
                "AudioService not started because config flags disable autostart "
                "(SC_AUDIO_ENABLE=%s, SC_AUDIO_AUTOSTART=%s)",
                config.enable,
                config.autostart,
            )

        # Poll status periodically so manual tests can confirm supervisor behavior.
        while not shutdown_event.wait(2.0):
            status = audio_service.status()
            LOGGER.info(
                "Audio status: state=%s pid=%s restarts=%s backoff=%s error=%s",
                status.state.value,
                status.pid,
                status.restart_count,
                status.backoff_s,
                status.last_error,
            )
    except KeyboardInterrupt:
        shutdown_event.set()
    finally:
        audio_service.stop()
        # Small delay keeps final log lines ordered during local interactive runs.
        time.sleep(0.1)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
