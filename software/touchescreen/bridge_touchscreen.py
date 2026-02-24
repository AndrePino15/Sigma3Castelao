from __future__ import annotations

import time
from enum import Enum
from typing import Any, Dict, Optional

from mqtt_client_touchscreen import MqttClient, MqttEvent


def section_root(section_id: int) -> str:
    return f"safegoals/section/{section_id}"


def emergency_topic() -> str:
    return "safegoals/emergency"


def control_topic(section_id: int) -> str:
    return f"{section_root(section_id)}/control"


def led_topic(section_id: int) -> str:
    return f"{section_root(section_id)}/led"


def status_topic(section_id: int) -> str:
    return f"{section_root(section_id)}/status"


class OperationMode(Enum):
    NORMAL = "NORMAL"
    SAFETY = "SAFETY"
    DEGRADED = "DEGRADED"


class Bridge:
    def __init__(
        self,
        section_id: int,
        broker_host: str,
        broker_port: int = 1883,
        touchscreen_seat_id: Optional[str] = None,
    ) -> None:
        self.section_id = section_id
        self.mode = OperationMode.NORMAL
        self.mqtt: Optional[MqttClient] = None
        self.broker_host = broker_host
        self.broker_port = broker_port
        self.touchscreen_seat_id = touchscreen_seat_id or str(section_id)

        self.status_topic = status_topic(self.section_id)
        self.compat_subscriptions: list[tuple[str, int]] = [
            (control_topic(self.section_id), 0),
            (led_topic(self.section_id), 0),
            (emergency_topic(), 1),
        ]

        self.server_control_topic = f"stadium/section/{self.section_id}/control"
        self.server_telemetry_topic = f"stadium/section/{self.section_id}/telemetry"
        self.touchscreen_cmd_topic = f"stadium/seat/{self.touchscreen_seat_id}/cmd"
        self.touchscreen_ack_topic = f"stadium/seat/{self.touchscreen_seat_id}/ack"
        self.touchscreen_telemetry_topic = f"stadium/seat/{self.touchscreen_seat_id}/telemetry"
        self.touchscreen_safety_topic = "stadium/broadcast/safety"
        self.touchscreen_replay_topic = "stadium/broadcast/replay"

        self.subscriptions: list[tuple[str, int]] = self.compat_subscriptions + [
            (self.server_control_topic, 1),
            (self.touchscreen_cmd_topic, 1),
            (self.touchscreen_safety_topic, 1),
            (self.touchscreen_replay_topic, 1),
        ]
        self._running = False

    def start(self) -> None:
        self.mqtt = MqttClient(
            broker_host=self.broker_host,
            broker_port=self.broker_port,
            client_id=f"section-{self.section_id}",
            keepalive=120,
            rx_maxsize=256,
        )
        connected = self.mqtt.connect(timeout=5.0)
        if not connected:
            self.mode = OperationMode.DEGRADED
            print(f"Connection to {self.broker_host}:{self.broker_port} failed.")
            return
        self.mqtt.subscribe(self.subscriptions)
        self._running = True

    def stop(self) -> None:
        self._running = False
        if self.mqtt is not None:
            self.mqtt.disconnect()
            self.mqtt = None

    def _publish_touchscreen_ack(self, ref_cmd: str, ok: bool, msg: str) -> None:
        if self.mqtt is None or not self.mqtt.is_connected():
            return
        self.mqtt.publish_json(
            self.touchscreen_ack_topic,
            {"ts": time.time(), "ok": ok, "ref_cmd": ref_cmd, "msg": msg},
            qos=1,
            retain=False,
        )

    def _publish_touchscreen_telemetry(self, message: str, payload: Optional[Dict[str, Any]] = None) -> None:
        if self.mqtt is None or not self.mqtt.is_connected():
            return
        body: Dict[str, Any] = {
            "ts": time.time(),
            "mode": self.mode.value,
            "device_id": self.touchscreen_seat_id,
            "rssi": 0,
            "metric": 1.0,
            "msg": message,
        }
        if payload:
            body["payload"] = payload
        self.mqtt.publish_json(self.touchscreen_telemetry_topic, body, qos=0, retain=False)

    def _publish_upstream_touch_event(self, cmd: str, payload: Dict[str, Any]) -> None:
        if self.mqtt is None or not self.mqtt.is_connected():
            return
        self.mqtt.publish_json(
            self.server_telemetry_topic,
            {
                "type": "touchscreen_cmd",
                "ts_ms": int(time.time() * 1000),
                "payload": {
                    "seat_id": self.touchscreen_seat_id,
                    "section_id": str(self.section_id),
                    "cmd": cmd,
                    "data": payload,
                },
            },
            qos=1,
            retain=False,
        )

    def _handle_server_control(self, payload: Dict[str, Any]) -> None:
        if self.mqtt is None or not self.mqtt.is_connected():
            return
        msg_type = str(payload.get("type", "")).lower()
        body = payload.get("payload")
        body = body if isinstance(body, dict) else {}

        if msg_type == "mode":
            mode_str = str(body.get("mode", "")).upper()
            if mode_str == "SAFETY":
                self.mode = OperationMode.SAFETY
            elif mode_str == "NORMAL":
                self.mode = OperationMode.NORMAL
            level = "CRITICAL" if self.mode == OperationMode.SAFETY else "INFO"
            reason = str(body.get("reason", "")).strip()
            self.mqtt.publish_json(
                self.touchscreen_safety_topic,
                {
                    "ts": time.time(),
                    "mode": self.mode.value,
                    "level": level,
                    "msg": reason or ("Safety mode enabled" if level == "CRITICAL" else "Safety cleared"),
                },
                qos=1,
                retain=True,
            )
            return

        if msg_type == "goal":
            self.mqtt.publish_json(
                self.touchscreen_replay_topic,
                {
                    "ts": time.time(),
                    "cmd": "REPLAY",
                    "clip": "goal",
                    "team": str(body.get("team", "home")),
                    "url": body.get("url", ""),
                },
                qos=1,
                retain=False,
            )
            return

        if msg_type in {"vote", "animation", "led"}:
            self._publish_touchscreen_telemetry(f"server_event:{msg_type}", body)

    def mqtt_handle(self, event: MqttEvent) -> None:
        topic = event.topic
        payload = event.payload if isinstance(event.payload, dict) else {}

        if topic == emergency_topic():
            self.mode = OperationMode.SAFETY
            self._publish_upstream_touch_event("EMERGENCY", {"source": "legacy_emergency_topic"})
            return

        if topic == self.touchscreen_safety_topic:
            req_mode = str(payload.get("mode", "")).upper()
            if req_mode == "SAFETY":
                self.mode = OperationMode.SAFETY
                self._publish_upstream_touch_event("SAFETY", payload)
            elif req_mode == "NORMAL":
                self.mode = OperationMode.NORMAL
                self._publish_upstream_touch_event("SAFETY_CLEAR", payload)
            return

        if topic == self.server_control_topic:
            self._handle_server_control(payload)
            return

        if topic == self.touchscreen_cmd_topic:
            cmd = str(payload.get("cmd", "")).upper()
            if not cmd:
                self._publish_touchscreen_ack("UNKNOWN", False, "Missing cmd field")
                return

            allowed = {
                "ORDER",
                "REPLAY",
                "VIDEO",
                "INFO",
                "ADMIN",
                "MATCH_STATS",
                "API_CONFIG",
                "STREAM",
                "SET_MODE",
                "SAFETY",
                "EMERGENCY",
                "LED_SET",
                "SET_LED",
            }
            if cmd not in allowed:
                self._publish_touchscreen_ack(cmd, False, f"Unknown command: {cmd}")
                return

            if cmd == "SET_MODE":
                mode_str = str(payload.get("mode", "")).upper()
                if mode_str == "SAFETY":
                    self.mode = OperationMode.SAFETY
                elif mode_str == "NORMAL":
                    self.mode = OperationMode.NORMAL

            if cmd in {"SAFETY", "EMERGENCY"}:
                self.mode = OperationMode.SAFETY

            self._publish_upstream_touch_event(cmd, payload)
            self._publish_touchscreen_ack(cmd, True, f"ACK for {cmd}")

    def run(self) -> None:
        if self.mqtt is None:
            raise RuntimeError("Bridge.start() must be called before Bridge.run().")

        last_heartbeat = time.time()
        try:
            while self._running:
                event = self.mqtt.get_rx(timeout=0.05)
                if event is not None:
                    self.mqtt_handle(event)

                now = time.time()
                if self.mqtt.is_connected() and (now - last_heartbeat) >= 1.0:
                    self.mqtt.publish_json(
                        self.status_topic,
                        {"section": self.section_id, "mode": self.mode.value, "alive": True},
                        qos=0,
                        retain=False,
                    )
                    self.mqtt.publish_json(
                        self.server_telemetry_topic,
                        {
                            "type": "heartbeat",
                            "ts_ms": int(now * 1000),
                            "payload": {
                                "section_id": str(self.section_id),
                                "seat_id": self.touchscreen_seat_id,
                                "mode": self.mode.value,
                                "alive": True,
                            },
                        },
                        qos=0,
                        retain=False,
                    )
                    self._publish_touchscreen_telemetry("bridge_alive")
                    last_heartbeat = now
        except KeyboardInterrupt:
            pass
        finally:
            self.stop()
