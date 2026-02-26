"""
Live microphone RTP/Opus streamer (server-side).

This module keeps the same public API expected by existing Flask routes:
  - start(target_ip=..., target_port=...)
  - stop()
  - status()
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional
import os
import subprocess
import threading


@dataclass
class AudioRtpConfig:
    default_ip: str = "127.0.0.1"
    default_port: int = 5004
    input_backend: str = ""
    input_device: str = ""
    opus_bitrate: str = "64k"


class AudioStreamer:
    """Small ffmpeg-based live audio sender (Mac mic -> Pi RTP/UDP)."""

    def __init__(
        self,
        cfg: Optional[AudioRtpConfig] = None,
        *,
        target_ip: Optional[str] = None,
        target_port: Optional[int] = None,
        input_backend: str = "",
        input_device: str = "",
        opus_bitrate: str = "64k",
    ) -> None:
        if cfg is None:
            cfg = AudioRtpConfig(
                default_ip=target_ip or "127.0.0.1",
                default_port=int(target_port or 5004),
                input_backend=input_backend,
                input_device=input_device,
                opus_bitrate=opus_bitrate or "64k",
            )
        self.cfg = cfg
        self._proc: Optional[subprocess.Popen] = None
        self._stderr_thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()
        self._last_error: Optional[str] = None

    def is_running(self) -> bool:
        return self._proc is not None and self._proc.poll() is None

    def status(self) -> dict:
        with self._lock:
            proc = self._proc
            return {
                "running": proc is not None and proc.poll() is None,
                "pid": proc.pid if proc is not None and proc.poll() is None else None,
                "last_error": self._last_error,
            }

    def _resolve_input(self) -> tuple[str, str]:
        backend = (self.cfg.input_backend or "").strip().lower()
        device = (self.cfg.input_device or "").strip()

        if not backend:
            if os.name == "posix" and "darwin" in os.uname().sysname.lower():
                backend = "avfoundation"
            else:
                backend = "alsa"

        if backend == "avfoundation":
            # avfoundation audio-only capture format is ":<audio_device_index>".
            audio_idx = device or "0"
            return backend, f":{audio_idx}"

        if backend == "alsa":
            return backend, device or "default"
        if backend == "pulse":
            return backend, device or "default"
        if backend == "dshow":
            # Windows DirectShow uses: audio=<device_name>
            return backend, device or "audio=default"

        # Last-resort fallback.
        return "avfoundation", ":0"

    def _read_stderr_forever(self, proc: subprocess.Popen) -> None:
        if proc.stderr is None:
            return
        try:
            for line in proc.stderr:
                text = line.strip()
                if text:
                    with self._lock:
                        self._last_error = text
        except Exception:
            return

    def start(self, target_ip: Optional[str] = None, target_port: Optional[int] = None, **kwargs) -> None:
        # Support alternate naming if callers pass ip/port.
        if target_ip is None:
            target_ip = kwargs.get("ip") or self.cfg.default_ip
        if target_port is None:
            target_port = int(kwargs.get("port") or self.cfg.default_port)

        with self._lock:
            self.cfg.default_ip = str(target_ip)
            self.cfg.default_port = int(target_port)

        if self.is_running():
            self.stop()

        backend, device = self._resolve_input()
        rtp_url = f"rtp://{target_ip}:{int(target_port)}"

        # Pi side expects RTP Opus payload=96 @ 48 kHz.
        cmd = [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "warning",
            "-fflags",
            "nobuffer",
            "-f",
            backend,
            "-i",
            device,
            "-ac",
            "1",
            "-ar",
            "48000",
            "-c:a",
            "libopus",
            "-application",
            "voip",
            "-frame_duration",
            "20",
            "-b:a",
            self.cfg.opus_bitrate,
            "-f",
            "rtp",
            "-payload_type",
            "96",
            rtp_url,
        ]

        with self._lock:
            self._last_error = None

        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
        )
        self._proc = proc
        self._stderr_thread = threading.Thread(
            target=self._read_stderr_forever, args=(proc,), daemon=True
        )
        self._stderr_thread.start()

    def stop(self) -> None:
        proc = self._proc
        self._proc = None
        if proc is None:
            return
        if proc.poll() is not None:
            return

        try:
            proc.terminate()
            proc.wait(timeout=2)
        except Exception:
            try:
                proc.kill()
            except Exception:
                pass
