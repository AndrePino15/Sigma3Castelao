"""GStreamer command builders for the audio worker.

This module only builds ``gst-launch-1.0`` argument lists and does not execute
them. Keeping pipeline construction here avoids mixing GStreamer specifics into
the worker control loop or the main-process supervisor.
"""

from __future__ import annotations

from typing import List

from .config import AudioConfig


def _build_alsasink_args(device: str | None) -> List[str]:
    """Return ``alsasink`` arguments, including ``device=...`` when configured."""
    if device:
        return ["alsasink", f"device={device}"]
    return ["alsasink"]


def build_fallback_cmd(config: AudioConfig) -> List[str]:
    """Build a fallback audio pipeline command for silence output.

    Returns a ``subprocess.Popen``-ready command list for ``gst-launch-1.0``.
    Raises ``ValueError`` for unsupported fallback modes or missing required
    fallback file paths.
    """
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
    """Build the RTP/Opus receive pipeline command expected by the worker.

    Phase 2/3 supports Opus only. The resulting command receives RTP over UDP,
    applies a jitter buffer using ``latency_target_ms``, decodes audio, and
    outputs to ALSA.
    """
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
