"""
RTP over UDP audio streamer (server -> Pi)

- Pure Python (no extra deps)
- Sends 16-bit PCM mono (L16-like) in RTP packets
- Designed for demo / coursework verification

Pi can verify with:
  sudo tcpdump -n udp port 5004
or Wireshark to see RTP packets arriving.
"""

from __future__ import annotations

import math
import os
import random
import socket
import struct
import threading
import time
from dataclasses import dataclass


@dataclass
class AudioRtpConfig:
    target_ip: str = "127.0.0.1"
    target_port: int = 5004
    sample_rate: int = 48000
    channels: int = 1
    payload_type: int = 96        # dynamic PT; easy for demos
    packet_ms: int = 20           # 20ms per RTP packet
    tone_hz: float = 1000.0       # test tone frequency
    tone_amp: float = 0.25        # 0..1


class RtpAudioStreamer:
    """
    Background RTP/UDP sender.
    """
    def __init__(self, cfg: AudioRtpConfig) -> None:
        self.cfg = cfg
        self._sock: socket.socket | None = None
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()

        self._seq = random.randint(0, 65535)
        self._ts = random.randint(0, 2**31 - 1)
        self._ssrc = random.randint(0, 2**32 - 1)

        self._phase = 0.0  # for tone gen

    def is_running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def start(self, target_ip: str | None = None, target_port: int | None = None) -> None:
        if self.is_running():
            return

        if target_ip:
            self.cfg.target_ip = target_ip
        if target_port:
            self.cfg.target_port = int(target_port)

        self._stop.clear()
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=1.0)
        self._thread = None
        if self._sock:
            try:
                self._sock.close()
            except Exception:
                pass
        self._sock = None

    # ----- Internals -----
    def _build_rtp_header(self, marker: int, payload_type: int, seq: int, ts: int, ssrc: int) -> bytes:
        # RTP v2: V=2,P=0,X=0,CC=0  => 0x80
        b0 = 0x80
        b1 = ((marker & 0x1) << 7) | (payload_type & 0x7F)
        return struct.pack("!BBHII", b0, b1, seq & 0xFFFF, ts & 0xFFFFFFFF, ssrc & 0xFFFFFFFF)

    def _gen_tone_pcm16(self, samples: int) -> bytes:
        # mono 16-bit signed little-endian
        sr = self.cfg.sample_rate
        w = 2.0 * math.pi * float(self.cfg.tone_hz) / float(sr)
        amp = max(0.0, min(1.0, float(self.cfg.tone_amp)))

        out = bytearray()
        for _ in range(samples):
            v = math.sin(self._phase) * amp
            self._phase += w
            if self._phase > 2.0 * math.pi:
                self._phase -= 2.0 * math.pi
            s = int(max(-1.0, min(1.0, v)) * 32767.0)
            out += struct.pack("<h", s)
        return bytes(out)

    def _run(self) -> None:
        assert self._sock is not None
        addr = (self.cfg.target_ip, int(self.cfg.target_port))

        samples_per_packet = int(self.cfg.sample_rate * self.cfg.packet_ms / 1000)
        pkt_interval = self.cfg.packet_ms / 1000.0

        next_send = time.perf_counter()

        while not self._stop.is_set():
            # Generate payload (PCM16)
            payload = self._gen_tone_pcm16(samples_per_packet)

            # RTP header
            hdr = self._build_rtp_header(
                marker=0,
                payload_type=self.cfg.payload_type,
                seq=self._seq,
                ts=self._ts,
                ssrc=self._ssrc,
            )

            # Send
            try:
                self._sock.sendto(hdr + payload, addr)
            except Exception:
                # If Wi-Fi drops, keep running; user can stop manually
                pass

            # Update RTP counters
            self._seq = (self._seq + 1) & 0xFFFF
            self._ts = (self._ts + samples_per_packet) & 0xFFFFFFFF

            # Timing
            next_send += pkt_interval
            now = time.perf_counter()
            sleep_s = next_send - now
            if sleep_s > 0:
                time.sleep(sleep_s)
            else:
                # If we fell behind, reset schedule
                next_send = now