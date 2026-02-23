from __future__ import annotations

from typing import List

from .config import AudioConfig


def _build_alsasink_args(device: str | None) -> List[str]:
    if device:
        return ["alsasink", f"device={device}"]
    return ["alsasink"]


def build_fallback_cmd(config: AudioConfig) -> List[str]:
    sink_args = _build_alsasink_args(config.alsa_device)

    if config.fallback_mode == "generate_silence":
        pipeline = [
            "gst-launch-1.0",
            "-q",
            "audiotestsrc",
            "wave=silence",
            "is-live=true",
            "!",
            "audioconvert",
            "!",
            "audioresample",
            "!",
            *sink_args,
        ]
        return pipeline

    if config.fallback_mode == "silence_file":
        path = config.fallback_path
        if not path:
            raise ValueError("fallback_path must be provided for silence_file mode")
        pipeline = [
            "gst-launch-1.0",
            "-q",
            "filesrc",
            f"location={path}",
            "!",
            "decodebin",
            "!",
            "audioconvert",
            "!",
            "audioresample",
            "!",
            *sink_args,
        ]
        return pipeline

    if config.fallback_mode == "none":
        raise ValueError("Fallback mode 'none' not supported in Phase 2")

    raise ValueError(f"Unsupported fallback mode {config.fallback_mode!r}")


def build_stream_cmd(config: AudioConfig) -> List[str]:
    if config.codec.lower() != "opus":
        raise ValueError("Only opus supported for stream in Phase 2")

    sink_args = _build_alsasink_args(config.alsa_device)
    caps = (
        "application/x-rtp,media=audio,"
        "encoding-name=OPUS,payload=96,clock-rate=48000"
    )

    return [
        "gst-launch-1.0",
        "-q",
        "udpsrc",
        f"port={config.listen_port}",
        f"caps={caps}",
        "!",
        "rtpjitterbuffer",
        f"latency={config.latency_target_ms}",
        "!",
        "rtpopusdepay",
        "!",
        "opusdec",
        "!",
        "audioconvert",
        "!",
        "audioresample",
        "!",
        *sink_args,
    ]


# TODO(Phase 3): integrate stream/fallback runner control.
