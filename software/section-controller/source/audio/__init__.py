"""Audio subsystem package.

This package defines the public audio-facing API used by ``main.py`` for service
orchestration while keeping runtime audio behavior inside the worker process.
``AudioService`` supervises the worker lifecycle and restart policy, and
``AudioConfig`` reads ``SC_AUDIO_*`` environment variables.
The worker implementation lives in ``audio.runner`` and owns stream/fallback
audio behavior.
"""

from .config import AudioConfig
from .service import AudioService
from .types import AudioState, AudioStatus

__all__ = ["AudioConfig", "AudioService", "AudioState", "AudioStatus"]
