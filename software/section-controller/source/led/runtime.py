from __future__ import annotations

from typing import Any, Dict, Optional

from .clock_sync import ShowClockEstimator
from .cue_store import CueStore
from .models import Cue, SectionLedStatus
from .renderer import LedRenderer
from .scheduler import FixedRateCanScheduler


class LedRuntime:
    """Incremental LED runtime skeleton; safe no-op until seat maps/CAN callback are wired."""

    def __init__(self, section_id: int) -> None:
        """Create runtime state for one section controller instance."""

        self.section_id = int(section_id)
        self.clock = ShowClockEstimator()
        self.cues = CueStore()
        self.renderer = LedRenderer()
        self.scheduler = FixedRateCanScheduler()
        self._last_scheduler_tick_ms: Optional[int] = None
        self._status = SectionLedStatus(engine="initialized")

    def handle_mqtt_led_command(self, payload: Dict[str, Any]) -> None:
        """Handle versioned LED cue commands received from MQTT."""

        inner = payload.get("payload") if isinstance(payload.get("payload"), dict) else payload
        if not isinstance(inner, dict) or inner.get("schema") != "led.cue.v1":
            return
        cmd = str(inner.get("cmd", "")).upper()
        if cmd == "CUE_START":
            cue_id = str(inner.get("cue_id", ""))
            if not cue_id:
                return
            cue = Cue(
                cue_id=cue_id,
                animation_id=str(inner.get("animation_id", "traveling_wave")),
                start_time_show_ms=int(inner.get("start_time_show_ms", 0)),
                duration_ms=int(inner["duration_ms"]) if inner.get("duration_ms") is not None else None,
                loop=bool(inner.get("loop", False)),
                scope=dict(inner.get("scope", {})) if isinstance(inner.get("scope"), dict) else {},
                params=dict(inner.get("params", {})) if isinstance(inner.get("params"), dict) else {},
            )
            self.cues.add_or_replace(cue)
        elif cmd == "CUE_STOP":
            cue_id = str(inner.get("cue_id", ""))
            if cue_id:
                self.cues.stop(cue_id)

    def handle_clock_sync(self, payload: Dict[str, Any]) -> None:
        """Update local show-clock estimator from a CLOCK_SYNC message."""

        # Runtime is clock-source agnostic; caller provides monotonic timestamp.
        import time
        self.clock.update_from_clock_sync(payload, time.monotonic())

    def tick(self, now_monotonic_s: float) -> None:
        """Advance runtime and run a scheduler sweep whenever a 10 Hz slot changes."""

        show_time_ms = self.clock.show_time_ms(now_monotonic_s)
        scheduler_tick_ms = (show_time_ms // 100) * 100
        if self._last_scheduler_tick_ms != scheduler_tick_ms:
            colors_now = self.renderer.render_frame(self.cues, scheduler_tick_ms)
            colors_next = self.renderer.render_frame(self.cues, scheduler_tick_ms + 50)
            self.scheduler.tick(colors_now, colors_next, scheduler_tick_ms)
            self._last_scheduler_tick_ms = scheduler_tick_ms
        snap = self.cues.snapshot(show_time_ms)
        self._status.engine = "running"
        self._status.show_time_ms = show_time_ms
        self._status.offset_ms = self.clock.offset_ms()
        self._status.active_cue_ids = snap.active_cue_ids
        self._status.render_mode = self.renderer.render_mode
        self._status.notes = ["skeleton_runtime"]

    def status_snapshot(self) -> Dict[str, Any]:
        """Return a serializable LED runtime status snapshot."""

        return {
            "engine": self._status.engine,
            "show_time_ms": self._status.show_time_ms,
            "clock_offset_ms": self._status.offset_ms,
            "active_cue_ids": list(self._status.active_cue_ids),
            "render_mode": self._status.render_mode,
            "notes": list(self._status.notes),
        }
