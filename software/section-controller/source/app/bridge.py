import canbus.protocol as protocol
from canbus.interface import CanInterface
from app.mqtt_client import MqttClient, MqttEvent
from app.mqtt_topics import control_topic, emergency_topic, led_topic, status_topic, show_clock_topic
from canbus.types import MessageTypes, OperationMode
try:
    from led.runtime import LedRuntime
except Exception:  # pragma: no cover - keep bridge startup tolerant during migration
    LedRuntime = None  # type: ignore[assignment]

import can
import logging
from typing import Any, Dict, Optional
import time

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
    """
    def __init__(self, section_id: int,
                 broker_host: str,
                 broker_port: int = 1883,
                 can_channel: str = "can0",
                 can_interface: str = "socketcan") -> None:
        
        self.section_id = section_id
        self.mode = OperationMode.NORMAL

        # Transport objects created in the constructor
        self.mqtt: Optional[MqttClient] = None
        self.can: Optional[CanInterface] =None

        # internal variables configuration
        self.broker_host = broker_host
        self.broker_port = broker_port 
        self.can_channel = can_channel
        self.can_interface = can_interface

        # The int inside each tupple defines the QoS for the subscription to that topic, which is a parameter 
        # from the MQTT protocol itself. 
        # QoS: emergency/control = 1 (more reliable), LED = 0 (best-effort)
        self.subscriptions: list[tuple[str, int]] = [(control_topic(self.section_id), 0),
                                              (led_topic(self.section_id), 0), 
                                              (show_clock_topic(), 0),
                                              (emergency_topic(), 1)]
        
        # Where this controller publishes aggregated status
        self.status_topic = status_topic(self.section_id)
        # simple run control
        self._running = False
        self._can_available = False
        self._can_recovery_next_ts = 0.0
        self._can_recovery_backoff_s = CAN_RECOVERY_BACKOFF_MIN_S
        self._can_recovery_attempts = 0
        self._can_failure_logged = False
        self._known_node_ids: set[int] = set()
        self._vote_request_sweep_pending = False
        self._vote_request_nodes_remaining: set[int] = set()
        self._led_runtime: Optional[Any] = None

# ================Methods for starting and stoping the controller================

    def start(self) -> None:
        '''
        This method is required to be called inside main.py to initialise the controller and both the MQTT Client and CAN bus.

        Its main functionalities are: connecting MQTT, starting CAN RX threads and apply CAN filters.
        '''
        LOGGER.info(
            "Bridge starting: section_id=%s broker=%s:%s can=%s/%s",
            self.section_id,
            self.broker_host,
            self.broker_port,
            self.can_channel,
            self.can_interface,
        )
        # Create MQTT client
        self.mqtt = MqttClient(broker_host=self.broker_host,
                               broker_port=self.broker_port,
                               client_id=f"section-{self.section_id}",
                               keepalive=120,
                               rx_maxsize=256)

        # Create CAN interface
        try:
            self.can = CanInterface(channel=self.can_channel,
                                    interface=self.can_interface,
                                    rx_maxsize=256)
        except Exception:
            LOGGER.exception(
                "Failed to initialize CAN interface %s/%s",
                self.can_channel,
                self.can_interface,
            )
            raise
        
        # Connect MQTT
        try:
            LOGGER.info("Connecting MQTT client to %s:%s", self.broker_host, self.broker_port)
            connection_success = self.mqtt.connect(timeout=5.0)
        except Exception:
            LOGGER.exception("MQTT connect raised an exception")
            connection_success = False
        if not connection_success:
            # For now, we don't crash; we go DEGRADED and keep CAN running.
            self.mode = OperationMode.DEGRADED
            LOGGER.warning("Connection to %s:%s failed; continuing in DEGRADED mode", self.broker_host, self.broker_port)
        else:
            LOGGER.info("MQTT connected; subscribing to %s topics", len(self.subscriptions))
            self.mqtt.subscribe(self.subscriptions)

        # Apply CAN filters to reduce load and seat->ctrl status range plus emergency/broadcast IDs
        self.can.set_filters(self._can_filters())

        # Start CAN RX thread (enqueues to self.can.rx_queue)
        self.can.start_rx(timeout=1.0)
        LOGGER.info("CAN RX thread started")

        self._can_available = True
        self._can_recovery_backoff_s = CAN_RECOVERY_BACKOFF_MIN_S
        self._can_recovery_next_ts = 0.0
        self._can_recovery_attempts = 0
        self._can_failure_logged = False
        self._running = True
        LOGGER.info("Bridge started successfully")

    def request_stop(self) -> None:
        """
        Request bridge loop shutdown without tearing down transports immediately.
        """
        self._running = False

    def stop(self) -> None:
        """
        This method stops loops and handles shutdown transports cleanly
        """
        self._running = False

        if self.mqtt is not None:
            self.mqtt.disconnect()
            self.mqtt = None
            LOGGER.info("MQTT Client disconnected")

        if self.can is not None:
            self.can.close()
            self.can = None
            LOGGER.info("CAN bus disconnected")
        self._can_available = False

# ================Methods for handling of the MQTT Client and CAN Bus================

    def mqtt_handle(self, event: MqttEvent) -> None:
        """
        This method handles one MQTT event: translate to CAN and/or update mode.
        """
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

        # Emergency topic is global
        if topic == emergency_topic():
            # Enter safety mode immediately
            self.mode = OperationMode.SAFETY

            # You can decide what CAN message represents emergency.
            # For now: broadcast an EMERGENCY message type on EMERGENCY_ID.
            msg = can.Message(
                arbitration_id=protocol.EMERGENCY_ID,
                data=[MessageTypes.EMERGENCY, 1, 0, 0, 0, 0, 0, 0],
                is_extended_id=False,
            )
            self._send_can_message(msg, context=f"emergency topic {topic}")
            return

        # I should take a look at this LED implementation to make sure it agrees with what is happening with the server. 
        # Shouldn't be too much of a problem
        # Section specific topics
        if topic == led_topic(self.section_id):
            if self._is_versioned_led_cue_payload(payload):
                runtime = self._get_led_runtime()
                if runtime is not None:
                    try:
                        runtime.handle_mqtt_led_command(payload)
                    except Exception:
                        LOGGER.exception("LED runtime failed to handle cue payload")
                return
            # Ignore LED commands in SAFETY mode
            if self.mode == OperationMode.SAFETY:
                return

            # Expect: {"seat": int, "rgb": [r,g,b]}
            seat = payload.get("seat")
            rgb = payload.get("rgb")

            if not isinstance(seat, int):
                return
            if (
                not isinstance(rgb, list)
                or len(rgb) != 3
                or not all(isinstance(x, int) for x in rgb)
            ):
                return

            r, g, b = rgb
            node_id = protocol.seat_cmd_id(seat)
            self._known_node_ids.add(node_id)
            msg = protocol.encode_led_set(
                seat=seat,
                r=r,
                g=g,
                b=b,
                vote_request=self._consume_vote_request_for_node(node_id),
                reply_request=False,
            )
            self._send_can_message(msg, context=f"LED command topic {topic}")
            return

    def _get_led_runtime(self) -> Optional[Any]:
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
        schema = payload.get("schema")
        if schema == "led.cue.v1":
            return True
        inner = payload.get("payload")
        if isinstance(inner, dict) and inner.get("schema") == "led.cue.v1":
            return True
        return False

        if topic == control_topic(self.section_id):
            # Supports both local legacy schema and server wrapped schema.
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
                # Ignore unimplemented wrapped control message types for now.
                return

            # Basic control schema examples:
            # {"cmd": "set_mode", "mode": "NORMAL"} or {"cmd":"safety", "enabled": true}
            cmd = payload.get("cmd")

            if cmd == "set_mode":
                self._apply_mode_value(payload.get("mode"))
                return

            if cmd == "safety":
                enabled = payload.get("enabled")
                if isinstance(enabled, bool):
                    self.mode = OperationMode.SAFETY if enabled else OperationMode.NORMAL
                return
            if cmd == "vote":
                self._arm_vote_request_sweep()
                return
            return

    def _can_filters(self) -> list[dict[str, object]]:
        """
        Return the CAN hardware filters used by this controller.
        """
        return [
            {"can_id": protocol.NODE_REPLY_ID, "can_mask": 0x7FF, "extended": False},
            {"can_id": protocol.EMERGENCY_ID, "can_mask": 0x7FF, "extended": False},
            {"can_id": protocol.BROADCAST_CMD_ID, "can_mask": 0x7FF, "extended": False},
        ]

    def _apply_mode_value(self, mode_value: Any) -> None:
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

    def _arm_vote_request_sweep(self) -> None:
        self._vote_request_sweep_pending = True
        self._vote_request_nodes_remaining = set(self._known_node_ids)
        LOGGER.info(
            "Armed vote request pulse (known_nodes=%s)",
            len(self._vote_request_nodes_remaining),
        )

    def _consume_vote_request_for_node(self, node_id: int) -> bool:
        """
        Set vote_request=1 once per known node on its next outbound frame.
        If no known nodes are registered yet, pulse the next outbound node frame.
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

    def _set_can_unavailable(self, reason: str) -> None:
        """
        Transition bridge into degraded mode and schedule CAN recovery retries.
        """
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
        """
        Transmit a CAN frame when CAN is available; degrade and schedule recovery on error.
        """
        if self.can is None or not self._can_available:
            LOGGER.info("Skipping CAN send while CAN unavailable (%s)", context)
            return
        try:
            self.can.send(msg)
        except Exception as exc:
            LOGGER.error("CAN send failed during %s: %s", context, exc)
            self._set_can_unavailable(f"TX failure: {exc}")

    def _attempt_can_recovery(self) -> None:
        """
        Recreate the CAN interface and RX thread, then swap it in on success.
        """
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
        """
        This method handles one CAN message: decode and forward to MQTT status.
        """
        if self.mqtt is None:
            return
        if not self.mqtt.is_connected():
            # In DEGRADED mode, or broker down: drop status for now
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
        """
        Run the bridge loop: consume MQTT and CAN queues and dispatch.
        """
        if self.mqtt is None or self.can is None:
            raise RuntimeError("Bridge.start() must be called before Bridge.run().")

        # Simple periodic heartbeat publishing (optional)
        last_heartbeat = time.time()

        try:
            while self._running:
                if self.can is not None and self._can_available and self.can.has_rx_failure():
                    reason = self.can.rx_error_summary() or "unknown RX error"
                    self._set_can_unavailable(f"RX failure: {reason}")

                if not self._can_available:
                    self._attempt_can_recovery()

                # Process a few MQTT events quickly
                event = self.mqtt.get_rx(timeout=0.05)
                if event is not None:
                    self.mqtt_handle(event)

                # Process a few CAN frames quickly
                if self.can is not None and self._can_available:
                    can_msg = self.can.get_rx(timeout=0.05)
                    if can_msg is not None:
                        self.can_handle(can_msg)

                runtime = self._led_runtime
                if runtime is not None:
                    try:
                        runtime.tick(time.monotonic())
                    except Exception:
                        LOGGER.exception("LED runtime tick failed")

                # Optional heartbeat/status every 1s
                now = time.time()
                if self.mqtt.is_connected() and (now - last_heartbeat) >= 1.0:
                    self.mqtt.publish_json(
                        self.status_topic,
                        {"section": self.section_id, "type": "section_heartbeat", "mode": self.mode.name, "alive": True},
                        qos=0,
                        retain=False,
                    )
                    last_heartbeat = now

        except KeyboardInterrupt:
            pass
        finally:
            self.stop()

    
