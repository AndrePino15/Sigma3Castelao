"""MQTT client wrapper (paho-mqtt).

Responsibilities:
- Connect to MQTT broker (and reconnect)
- Subscribe to telemetry topic
- Provide `publish()` for control messages
- Parse incoming telemetry JSON and update in-memory state

Design:
- The MQTT network loop runs in its own thread via `loop_start()`.
- Flask handlers call `publish()` from the main thread.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, Optional

import paho.mqtt.client as mqtt

from .config import Config
from . import state


log = logging.getLogger("sigma3.mqtt")


class MqttClient:
    def __init__(self, cfg: Config):
        self.cfg = cfg
        self.client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
        if cfg.mqtt_username:
            self.client.username_pw_set(cfg.mqtt_username, cfg.mqtt_password)

        # Register callbacks
        self.client.on_connect = self._on_connect
        self.client.on_message = self._on_message
        self.client.on_disconnect = self._on_disconnect

        self._started = False

    def start(self) -> None:
        """Connect and start background loop."""
        if self._started:
            return
        self.client.connect(self.cfg.mqtt_host, self.cfg.mqtt_port, keepalive=30)
        self.client.loop_start()
        self._started = True
        log.info("MQTT loop started")

    def stop(self) -> None:
        if not self._started:
            return
        self.client.loop_stop()
        self.client.disconnect()
        self._started = False
        log.info("MQTT loop stopped")

    def publish(self, topic: str, payload: Dict[str, Any], qos: int = 0, retain: bool = False) -> None:
        """Publish a JSON dict payload."""
        data = json.dumps(payload, separators=(",", ":"), ensure_ascii=False)
        self.client.publish(topic, data, qos=qos, retain=retain)
        log.info("Published to %s: %s", topic, data)

    # ===== Callbacks =====
    def _on_connect(self, client: mqtt.Client, userdata: Any, flags: Dict[str, Any], reason_code: int, properties=None):
        if reason_code == 0:
            log.info("Connected to broker %s:%s", self.cfg.mqtt_host, self.cfg.mqtt_port)
            # Subscribe to telemetry
            client.subscribe(self.cfg.mqtt_telemetry_topic)
            log.info("Subscribed to telemetry topic: %s", self.cfg.mqtt_telemetry_topic)
        else:
            log.error("Failed to connect, reason_code=%s", reason_code)

    def _on_disconnect(self, client: mqtt.Client, userdata: Any, reason_code: int, properties=None):
        log.warning("Disconnected from MQTT broker (reason_code=%s)", reason_code)

    def _on_message(self, client: mqtt.Client, userdata: Any, msg: mqtt.MQTTMessage):
        """Handle telemetry messages."""
        try:
            text = msg.payload.decode("utf-8", errors="replace")
            payload = json.loads(text)
            if isinstance(payload, dict):
                state.update_from_telemetry(payload)
        except Exception as e:
            log.exception("Bad telemetry on %s: %s", msg.topic, e)
