"""Audio configuration loading for the section-controller audio subsystem.

This module is intentionally small: it converts ``SC_AUDIO_*`` environment
variables into a typed ``AudioConfig`` object used by both the supervisor and
the worker process. Parsing is forgiving and falls back to defaults on invalid
values so startup remains predictable in field deployments.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Literal, Optional, cast


def _env_bool(name: str, default: bool) -> bool:
    """Read a boolean-like environment variable with a safe fallback."""
    raw = os.getenv(name)
    if raw is None:
        return default
    # check if the raw is true or false, giving different alternatives to write it
    # .strip() jsut gets rid of all the white spaces
    value = raw.strip().lower()
    if value in {"1", "true", "yes", "on"}:
        return True
    if value in {"0", "false", "no", "off"}:
        return False
    return default


def _env_int(name: str, default: int) -> int:
    """Read an integer environment variable, returning ``default`` on parse errors."""
    raw = os.getenv(name)
    if raw is None or raw.strip() == "":
        return default
    try:
        return int(raw.strip())
    except ValueError:
        return default


def _env_str(name: str, default: str) -> str:
    """Read a string environment variable and strip whitespace."""
    raw = os.getenv(name)
    return default if raw is None else raw.strip()


@dataclass(frozen=True)
class AudioConfig:
    """Immutable audio runtime configuration loaded from environment variables.

    The same structure is used by:
    - ``audio.service`` in the main process (supervision/spawn parameters)
    - ``audio.runner`` in the worker process (pipeline mode/latency settings)

    Create instances with ``AudioConfig.from_env()`` to keep defaults consistent
    across both sides of the subsystem.
    """

    enable: bool
    autostart: bool
    listen_port: int
    codec: str
    latency_target_ms: int
    loss_timeout_ms: int
    sink: str = "alsa"
    alsa_device: Optional[str] = None
    fallback_mode: Literal["generate_silence", "silence_file", "none"] = "generate_silence"
    fallback_path: Optional[str] = None
    fallback_crossfade_ms: int = 100
    log_level: str = "INFO"

    # This @classmethod decorator basically turns this method into one that takes the class itself as an argument (cls)
    # and not and instance of said class (self). This means that we can call it in the class without creating an object first
    @classmethod
    def from_env(cls) -> "AudioConfig":
        """Build an ``AudioConfig`` from ``SC_AUDIO_*`` environment variables.

        Invalid or missing values fall back to documented defaults instead of
        raising. This keeps service startup robust on partially configured hosts.
        """
        fallback_mode_raw = _env_str("SC_AUDIO_FALLBACK_MODE", "generate_silence") or "generate_silence"
        if fallback_mode_raw not in {"generate_silence", "silence_file", "none"}:
            # Literal means that fallbacl_mode can only be a string type of one of these 3 strings
            fallback_mode: Literal["generate_silence", "silence_file", "none"] = "generate_silence"
        else:
            fallback_mode = cast(Literal["generate_silence", "silence_file", "none"], fallback_mode_raw)

        alsa_device_raw = _env_str("SC_AUDIO_ALSA_DEVICE", "")
        fallback_path_raw = _env_str("SC_AUDIO_FALLBACK_PATH", "")

        return cls(
            enable=_env_bool("SC_AUDIO_ENABLE", True),
            autostart=_env_bool("SC_AUDIO_AUTOSTART", True),
            listen_port=_env_int("SC_AUDIO_RTP_PORT", 5004),
            codec=_env_str("SC_AUDIO_CODEC", "opus") or "opus",
            latency_target_ms=_env_int("SC_AUDIO_LATENCY_MS", 100),
            loss_timeout_ms=_env_int("SC_AUDIO_LOSS_TIMEOUT_MS", 300),
            sink=_env_str("SC_AUDIO_SINK", "alsa") or "alsa",
            alsa_device=alsa_device_raw or None,
            fallback_mode=fallback_mode,
            fallback_path=fallback_path_raw or None,
            fallback_crossfade_ms=100,
            log_level=_env_str("SC_AUDIO_LOG_LEVEL", "INFO") or "INFO",
        )
