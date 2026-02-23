"""Audio subsystem package (Phase 1).

Environment variables are read via ``AudioConfig.from_env()`` (``SC_AUDIO_*``).
Phase 2 will implement the GStreamer RTP -> ALSA pipeline in a process-isolated worker.
"""

from .config import AudioConfig
from .service import AudioService
from .types import AudioState, AudioStatus

__all__ = ["AudioConfig", "AudioService", "AudioState", "AudioStatus"]
