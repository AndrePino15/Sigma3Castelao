from __future__ import annotations

import logging
import os
from pathlib import Path
import time
from typing import Any, Dict, Optional

import can

import canbus.protocol as protocol
from app.mqtt_client import MqttClient, MqttEvent
from app.mqtt_topics import control_topic, emergency_topic, led_topic, show_clock_topic, status_topic
from canbus.interface import CanInterface
from canbus.types import MessageTypes, OperationMode

try:
    from led.runtime import LedRuntime
    from led.seat_map import load_section_seat_map
except Exception:  # pragma: no cover - keep bridge startup tolerant during migration
    LedRuntime = None  # type: ignore[assignment]
    load_section_seat_map = None  # type: ignore[assignment]

LOGGER = logging.getLogger(__name__)
CAN_RECOVERY_BACKOFF_MIN_S = 0.5
CAN_RECOVERY_BACKOFF_MAX_S = 5.0


class Bridge:
    """
    Section Controller bridge between MQTT (Wi-Fi) and CAN (seat bus).
    - Consumes queued MQTT events (from MqttClient)
    - Consumes queued CAN frames (from CanInterface)
    - Translates MQTT -> CAN commands
    - Forwards CAN -> MQTT status
    - Runs local LED runtime/scheduler for cue-based rendering
    """

    def __init__(
        self,
        section_id: int,
        broker_host: str,
        broker_port: int = 1883,
        can_channel: str = "can0",
        can_interface: str = "socketcan",
    ) -> None:
        self.section_id = section_id
        self.mode = OperationMode.NORMAL

        # Transport objects created in start()
        self.mqtt: Optional[MqttClient] = None
        self.can: Optional[CanInterface] = None

        self.broker_host = broker_host
        self.broker_port = broker_port
        self.can_channel = can_channel
        self.can_interface = can_interface

        # QoS: emergency/control = reliable, LED/clock = best-effort.
        self.subscriptions: list[tuple[str, int]] = [
            (control_topic(self.section_id), 1),
            (led_topic(self.section_id), 0),
            (show_clock_topic(), 0),
            (emergency_topic(), 1),
        ]

        self.status_topic = status_topic(self.section_id)

        self._running = False
        self._can_available = False
        self._can_recovery_next_ts = 0.0
        self._can_recovery_backoff_s = CAN_RECOVERY_BACKOFF_MIN_S
        self._can_recovery_attempts = 0
        self._can_failure_logged = False

        # Vote/reply policy state.
        self._known_node_ids: set[int] = set()
        self._vote_request_sweep_pending = False
        self._vote_request_nodes_remaining: set[int] = set()
        self._reply_request_period_ticks = 5
        self._scheduler_tick_index = 0
        self._reply_request_active = False

        # LED runtime state.
        self._led_runtime: Optional[Any] = None
        self._led_runtime_enabled = False

    def start(self) -> None:
        """Initialize MQTT/CAN transports, subscriptions, and optional LED runtime."""
        LOGGER.info(
            "Bridge starting: section_id=%s broker=%s:%s can=%s/%s",
            self.section_id,
            self.broker_host,
            self.broker_port,
            self.can_channel,
            self.can_interface,
        )

        self.mqtt = MqttClient(
            broker_host=self.broker_host,
            broker_port=self.broker_port,
            client_id=f"section-{self.section_id}",
            keepalive=120,
            rx_maxsize=256,
        )

        try:
            self.can = CanInterface(channel=self.can_channel, interface=self.can_interface, rx_maxsize=256)
        except Exception:
            LOGGER.exception("Failed to initialize CAN interface %s/%s", self.can_channel, self.can_interface)
            raise

        try:
            LOGGER.info("Connecting MQTT client to %s:%s", self.broker_host, self.broker_port)
            connection_success = self.mqtt.connect(timeout=5.0)
        except Exception:
            LOGGER.exception("MQTT connect raised an exception")
            connection_success = False

        if not connection_success:
            self.mode = OperationMode.DEGRADED
            LOGGER.warning(
                "Connection to %s:%s failed; continuing in DEGRADED mode",
                self.broker_host,
                self.broker_port,
            )
        else:
            LOGGER.info("MQTT connected; subscribing to %s topics", len(self.subscriptions))
            self.mqtt.subscribe(self.subscriptions)

        self.can.set_filters(self._can_filters())
        self.can.start_rx(timeout=1.0)
        LOGGER.info("CAN RX thread started")

        self._can_available = True
        self._can_recovery_backoff_s = CAN_RECOVERY_BACKOFF_MIN_S
        self._can_recovery_next_ts = 0.0
        self._can_recovery_attempts = 0
        self._can_failure_logged = False
        self._running = True

        self._configure_led_runtime()
        LOGGER.info("Bridge started successfully")

    def request_stop(self) -> None:
        """Request bridge loop shutdown without tearing down transports immediately."""
        self._running = False

    def stop(self) -> None:
        """Stop bridge loop and close MQTT/CAN transports."""
        self._running = False

        if self.mqtt is not None:
            self.mqtt.disconnect()
            self.mqtt = None
            LOGGER.info("MQTT client disconnected")

        if self.can is not None:
            self.can.close()
            self.can = None
            LOGGER.info("CAN bus disconnected")
        self._can_available = False

    def mqtt_handle(self, event: MqttEvent) -> None:
        """Handle one MQTT event and dispatch to runtime/protocol handlers."""
        topic = event.topic
        payload = event.payload or {}

        if topic == show_clock_topic():
            runtime = self._get_led_runtime()
            if runtime is not None:
                try:
                    runtime.handle_clock_sync(payload)
                except Exception:
                    LOGGER.exception("LED runtime failed to handle clock sync payload")
            return

        if topic == emergency_topic():
            self.mode = OperationMode.SAFETY
            runtime = self._get_led_runtime()
            if runtime is not None:
                runtime.handle_emergency(True)
            msg = can.Message(
                arbitration_id=protocol.EMERGENCY_ID,
                data=[MessageTypes.EMERGENCY, 1, 0, 0, 0, 0, 0, 0],
                is_extended_id=False,
            )
            self._send_can_message(msg, context=f"emergency topic {topic}")
            return

        if topic == led_topic(self.section_id):
            if self._is_versioned_led_cue_payload(payload):
                runtime = self._get_led_runtime()
                if runtime is not None:
                    try:
                        runtime.handle_mqtt_led_command(payload)
                    except Exception:
                        LOGGER.exception("LED runtime failed to handle cue payload")
                return

            # LEGACY LED payload support.
            if self.mode == OperationMode.SAFETY:
                return
            seat = payload.get("seat")
            rgb = payload.get("rgb")
            if not isinstance(seat, int):
                return
            if not isinstance(rgb, list) or len(rgb) != 3 or not all(isinstance(x, int) for x in rgb):
                return
            node_id = protocol.seat_cmd_id(seat)
            self._known_node_ids.add(node_id)
            msg = protocol.encode_led_set(
                seat=seat,
                r=rgb[0],
                g=rgb[1],
                b=rgb[2],
                vote_request=self._consume_vote_request_for_node(node_id),
                reply_request=self._reply_request_for_node(node_id),
            )
            self._send_can_message(msg, context=f"legacy LED command topic {topic}")
            return

        if topic == control_topic(self.section_id):
            self._handle_control_payload(payload)

    def _handle_control_payload(self, payload: Dict[str, Any]) -> None:
        """Handle wrapped and legacy control payload variants."""
        wrapped_type = payload.get("type")
        wrapped_payload = payload.get("payload")
        if isinstance(wrapped_type, str):
            inner = wrapped_payload if isinstance(wrapped_payload, dict) else {}
            if wrapped_type == "vote":
                self._arm_vote_request_sweep()
                return
            if wrapped_type == "mode":
                self._apply_mode_value(inner.get("mode"))
                return
            # Ignore wrapped goal/animation/etc on section controller.
            return

        cmd = payload.get("cmd")
        if cmd == "set_mode":
            self._apply_mode_value(payload.get("mode"))
            return
        if cmd == "safety":
            enabled = payload.get("enabled")
            if isinstance(enabled, bool):
                self.mode = OperationMode.SAFETY if enabled else OperationMode.NORMAL
                runtime = self._get_led_runtime()
                if runtime is not None:
                    runtime.handle_emergency(enabled)
            return
        if cmd == "vote":
            self._arm_vote_request_sweep()
            return

    def _configure_led_runtime(self) -> None:
        """Load seat map and wire LED runtime scheduler callbacks."""
        runtime = self._get_led_runtime()
        if runtime is None or load_section_seat_map is None:
            LOGGER.info("LED runtime unavailable; continuing without local LED scheduler")
            return

        if not self._env_bool("SC_LED_ENABLE", default=True):
            LOGGER.info("LED runtime disabled via SC_LED_ENABLE")
            return

        default_map_path = Path(__file__).resolve().parents[1] / "seat_map.json"
        map_path = Path(os.getenv("SC_SEAT_MAP_PATH", str(default_map_path)))
        if not map_path.is_file():
            LOGGER.warning("Seat map file not found at %s; LED runtime disabled", map_path)
            return

        try:
            seat_map = load_section_seat_map(map_path, expected_section_id=self.section_id)
        except Exception:
            LOGGER.exception("Failed loading seat map from %s; LED runtime disabled", map_path)
            return

        self._known_node_ids = {seat.node_id for seat in seat_map.seats}
        self._reply_request_period_ticks = max(1, int(os.getenv("SC_REPLY_REQUEST_PERIOD_TICKS", "5")))
        render_mode = os.getenv("SC_LED_RENDER_MODE", "seat").strip().lower() or "seat"
        runtime.configure(
            seat_map=seat_map,
            send_can=lambda msg: self._send_can_message(msg, context="LED runtime scheduler"),
            vote_request_for_node=self._consume_vote_request_for_node,
            reply_request_for_node=self._reply_request_for_node,
            on_scheduler_tick_start=self._on_led_scheduler_tick,
            render_mode=render_mode,
        )
        self._led_runtime_enabled = True
        LOGGER.info(
            "LED runtime configured: seat_map=%s seats=%s render_mode=%s reply_period_ticks=%s",
            map_path,
            len(seat_map.seats),
            render_mode,
            self._reply_request_period_ticks,
        )

    def _get_led_runtime(self) -> Optional[Any]:
        """Lazy-initialize LED runtime object."""
        if self._led_runtime is not None:
            return self._led_runtime
        if LedRuntime is None:
            return None
        try:
            self._led_runtime = LedRuntime(section_id=self.section_id)
        except Exception:
            LOGGER.exception("Failed to initialize LED runtime")
            self._led_runtime = None
        return self._led_runtime

    def _is_versioned_led_cue_payload(self, payload: Dict[str, Any]) -> bool:
        """Return True for cue messages using schema led.cue.v1."""
        if payload.get("schema") == "led.cue.v1":
            return True
        inner = payload.get("payload")
        return isinstance(inner, dict) and inner.get("schema") == "led.cue.v1"

    def _can_filters(self) -> list[dict[str, object]]:
        """Return CAN hardware filters used by this controller."""
        return [
            {"can_id": protocol.NODE_REPLY_ID, "can_mask": 0x7FF, "extended": False},
            {"can_id": protocol.EMERGENCY_ID, "can_mask": 0x7FF, "extended": False},
            {"can_id": protocol.BROADCAST_CMD_ID, "can_mask": 0x7FF, "extended": False},
        ]

    def _apply_mode_value(self, mode_value: Any) -> None:
        """Update operation mode from control payload string."""
        if not isinstance(mode_value, str):
            return
        mode_str = mode_value.strip().upper()
        if mode_str == "NORMAL":
            self.mode = OperationMode.NORMAL
        elif mode_str == "SAFETY":
            self.mode = OperationMode.SAFETY
        elif mode_str == "ID_ASSIGNMENT":
            self.mode = OperationMode.ID_ASSIGNMENT
        elif mode_str == "DEGRADED":
            self.mode = OperationMode.DEGRADED
        runtime = self._get_led_runtime()
        if runtime is not None:
            runtime.handle_emergency(self.mode == OperationMode.SAFETY)

    def _arm_vote_request_sweep(self) -> None:
        """Arm vote_request pulses for one full known-node sweep."""
        self._vote_request_sweep_pending = True
        self._vote_request_nodes_remaining = set(self._known_node_ids)
        LOGGER.info("Armed vote request pulse (known_nodes=%s)", len(self._vote_request_nodes_remaining))

    def _consume_vote_request_for_node(self, node_id: int) -> bool:
        """
        Return True when a given node frame should set vote_request=1.
        Pulses once per known node for each armed sweep.
        """
        if not self._vote_request_sweep_pending:
            return False
        if not self._vote_request_nodes_remaining:
            self._vote_request_sweep_pending = False
            return True
        if node_id not in self._vote_request_nodes_remaining:
            return False
        self._vote_request_nodes_remaining.discard(node_id)
        if not self._vote_request_nodes_remaining:
            self._vote_request_sweep_pending = False
        return True

    def _on_led_scheduler_tick(self, show_time_ms: int) -> None:
        """Track scheduler ticks and arm periodic reply requests."""
        self._scheduler_tick_index += 1
        self._reply_request_active = (self._scheduler_tick_index % self._reply_request_period_ticks) == 0

    def _reply_request_for_node(self, node_id: int) -> bool:
        """Return True when current scheduler tick should request node replies."""
        return (
            self._reply_request_active
            and node_id in self._known_node_ids
            and self.mode in (OperationMode.NORMAL, OperationMode.DEGRADED)
        )

    def _set_can_unavailable(self, reason: str) -> None:
        """Transition into degraded mode and schedule CAN recovery retries."""
        was_available = self._can_available
        if was_available and not self._can_failure_logged:
            LOGGER.error(
                "CAN runtime failure detected (%s); switching to DEGRADED mode and scheduling recovery",
                reason,
            )
        elif not self._can_failure_logged:
            LOGGER.error("CAN unavailable: %s", reason)

        self._can_available = False
        self._can_failure_logged = True
        if was_available:
            self._can_recovery_attempts = 0
            self._can_recovery_backoff_s = CAN_RECOVERY_BACKOFF_MIN_S
            self._can_recovery_next_ts = time.time() + self._can_recovery_backoff_s
        if self.mode == OperationMode.NORMAL:
            self.mode = OperationMode.DEGRADED

    def _send_can_message(self, msg: can.Message, *, context: str) -> None:
        """Transmit one CAN frame while handling runtime failures."""
        if self.can is None or not self._can_available:
            LOGGER.info("Skipping CAN send while CAN unavailable (%s)", context)
            return
        try:
            self.can.send(msg)
        except Exception as exc:
            LOGGER.error("CAN send failed during %s: %s", context, exc)
            self._set_can_unavailable(f"TX failure: {exc}")

    def _attempt_can_recovery(self) -> None:
        """Recreate the CAN interface and RX thread, then swap it in on success."""
        now = time.time()
        if self._running is False or self._can_available or self.can is None:
            return
        if now < self._can_recovery_next_ts:
            return

        self._can_recovery_attempts += 1
        LOGGER.info(
            "Attempting CAN recovery #%s on %s/%s (backoff=%.1fs)",
            self._can_recovery_attempts,
            self.can_channel,
            self.can_interface,
            self._can_recovery_backoff_s,
        )

        old_can = self.can
        new_can: Optional[CanInterface] = None
        try:
            new_can = CanInterface(channel=self.can_channel, interface=self.can_interface, rx_maxsize=256)
            new_can.set_filters(self._can_filters())
            new_can.start_rx(timeout=1.0)
        except Exception as exc:
            LOGGER.warning("CAN recovery attempt failed: %s", exc)
            if new_can is not None:
                try:
                    new_can.close()
                except Exception:
                    LOGGER.exception("Failed to close partially initialized CAN interface during recovery")
            self._can_recovery_next_ts = time.time() + self._can_recovery_backoff_s
            self._can_recovery_backoff_s = min(self._can_recovery_backoff_s * 2.0, CAN_RECOVERY_BACKOFF_MAX_S)
            return

        self.can = new_can
        self._can_available = True
        self._can_failure_logged = False
        self._can_recovery_backoff_s = CAN_RECOVERY_BACKOFF_MIN_S
        self._can_recovery_next_ts = 0.0
        self._can_recovery_attempts = 0
        if self.mode == OperationMode.DEGRADED:
            self.mode = OperationMode.NORMAL
        LOGGER.info("CAN recovery successful; CAN RX thread restarted")

        try:
            old_can.close()
        except Exception:
            LOGGER.exception("Failed to close previous CAN interface after successful recovery")

    def can_handle(self, msg: can.Message) -> None:
        """Handle one CAN RX frame and publish decoded seat status to MQTT."""
        if self.mqtt is None or not self.mqtt.is_connected():
            return

        try:
            decoded = protocol.decode(msg)
        except Exception:
            LOGGER.info("Unable to decode receive CAN msg: %s", msg)
            return

        node_id = decoded.get("node_id")
        if isinstance(node_id, int):
            self._known_node_ids.add(node_id)

        payload: Dict[str, Any] = {
            "section": self.section_id,
            "type": "seat_event",
            "mode": self.mode.name,
            "seat_id": decoded.get("seat"),
            "node_id": node_id,
            "sos": bool(decoded.get("sos", False)),
            "occupied": bool(decoded.get("occupied", False)),
            "voted": bool(decoded.get("voted", False)),
            "vote": decoded.get("vote"),
        }

        try:
            self.mqtt.publish_json(self.status_topic, payload, qos=0, retain=False)
        except Exception:
            LOGGER.exception("Failed to publish CAN status to MQTT topic %s", self.status_topic)

    def run(self) -> None:
        """Run main bridge loop: MQTT, CAN, LED runtime ticks, and heartbeat status."""
        if self.mqtt is None or self.can is None:
            raise RuntimeError("Bridge.start() must be called before Bridge.run().")

        last_heartbeat = time.time()
        try:
            while self._running:
                if self.can is not None and self._can_available and self.can.has_rx_failure():
                    reason = self.can.rx_error_summary() or "unknown RX error"
                    self._set_can_unavailable(f"RX failure: {reason}")

                if not self._can_available:
                    self._attempt_can_recovery()

                event = self.mqtt.get_rx(timeout=0.05)
                if event is not None:
                    self.mqtt_handle(event)

                if self.can is not None and self._can_available:
                    can_msg = self.can.get_rx(timeout=0.05)
                    if can_msg is not None:
                        self.can_handle(can_msg)

                runtime = self._led_runtime
                if runtime is not None and self._led_runtime_enabled:
                    try:
                        runtime.tick(time.monotonic())
                    except Exception:
                        LOGGER.exception("LED runtime tick failed")

                now = time.time()
                if self.mqtt.is_connected() and (now - last_heartbeat) >= 1.0:
                    hb: Dict[str, Any] = {
                        "section": self.section_id,
                        "type": "section_heartbeat",
                        "mode": self.mode.name,
                        "alive": True,
                    }
                    if runtime is not None and self._led_runtime_enabled:
                        hb["led_runtime"] = runtime.status_snapshot()
                    self.mqtt.publish_json(self.status_topic, hb, qos=0, retain=False)
                    last_heartbeat = now

        except KeyboardInterrupt:
            pass
        finally:
            self.stop()

    def _env_bool(self, name: str, *, default: bool) -> bool:
        """Parse boolean environment variable with a default fallback."""
        raw = os.getenv(name)
        if raw is None:
            return default
        normalized = raw.strip().lower()
        if normalized in ("1", "true", "yes", "on"):
            return True
        if normalized in ("0", "false", "no", "off"):
            return False
        return default
