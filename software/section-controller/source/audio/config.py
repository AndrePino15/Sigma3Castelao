from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Literal, Optional, cast


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    value = raw.strip().lower()
    if value in {"1", "true", "yes", "on"}:
        return True
    if value in {"0", "false", "no", "off"}:
        return False
    return default


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None or raw.strip() == "":
        return default
    try:
        return int(raw.strip())
    except ValueError:
        return default


def _env_str(name: str, default: str) -> str:
    raw = os.getenv(name)
    return default if raw is None else raw.strip()


@dataclass(frozen=True)
class AudioConfig:
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

    @classmethod
    def from_env(cls) -> "AudioConfig":
        fallback_mode_raw = _env_str("SC_AUDIO_FALLBACK_MODE", "generate_silence") or "generate_silence"
        if fallback_mode_raw not in {"generate_silence", "silence_file", "none"}:
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
