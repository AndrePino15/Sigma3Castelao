"""MQTT client wrapper (paho-mqtt).

- Connects to broker
- Subscribes to status wildcard topic
- Calls state.update_telemetry() when status messages arrive
"""
import json
import threading
from typing import Any, Callable, Optional

import paho.mqtt.client as mqtt

from .runtime_config import RuntimeConfig
from . import state
from .mqtt_topics import status_wildcard

class MqttClient:
    def __init__(self, cfg: RuntimeConfig):
        self.cfg = cfg
        self._client = mqtt.Client()
        self._thread: Optional[threading.Thread] = None

        self._client.on_connect = self._on_connect
        self._client.on_message = self._on_message

    def start(self) -> None:
        # Connect and start network loop in background.
        self._client.connect(self.cfg.mqtt_host, self.cfg.mqtt_port, keepalive=30)
        self._client.loop_start()

    def publish(self, topic: str, msg: Any) -> None:
        payload = json.dumps(msg)
        self._client.publish(topic, payload=payload, qos=0, retain=False)

    def _on_connect(self, client, userdata, flags, rc):
        # Subscribe to status/telemetry only (per teammate message).
        client.subscribe(status_wildcard())

    def _on_message(self, client, userdata, msg):
        # Status topic is safegoals/section/<id>/status
        try:
            topic = msg.topic
            parts = topic.split("/")
            # parts: ["safegoals","section","<id>","status"]
            section_id = parts[2] if len(parts) >= 4 else "?"
            data = json.loads(msg.payload.decode("utf-8"))
            state.update_telemetry(section_id, data)
        except Exception:
            # swallow errors in demo; you can log later
            return
