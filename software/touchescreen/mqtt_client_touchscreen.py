from __future__ import annotations

import json
import queue
import threading
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

import paho.mqtt.client as mqtt


@dataclass(frozen=True)
class MqttEvent:
    topic: str
    payload: Any
    qos: int = 0
    retain: bool = False


class MqttClient:
    def __init__(
        self,
        broker_host: str,
        broker_port: int = 1883,
        client_id: Optional[str] = None,
        username: Optional[str] = None,
        password: Optional[str] = None,
        keepalive: int = 60,
        rx_maxsize: int = 0,
    ) -> None:
        self.broker_host = broker_host
        self.broker_port = broker_port
        self.keepalive = keepalive
        self.rx_queue: "queue.Queue[MqttEvent]" = queue.Queue(maxsize=rx_maxsize)
        self._connected_event = threading.Event()
        self._client = mqtt.Client(client_id=client_id, clean_session=True)

        if username is not None:
            self._client.username_pw_set(username=username, password=password)

        self._client.on_connect = self._on_connect
        self._client.on_disconnect = self._on_disconnect
        self._client.on_message = self._on_message
        self._client.reconnect_delay_set(min_delay=1, max_delay=10)

    def _on_connect(self, client: mqtt.Client, userdata: Any, flags: Dict[str, Any], rc: int) -> None:
        if rc == 0:
            self._connected_event.set()
        else:
            self._connected_event.clear()

    def _on_disconnect(self, client: mqtt.Client, userdata: Any, rc: int) -> None:
        self._connected_event.clear()

    def _on_message(self, client: mqtt.Client, userdata: Any, msg: mqtt.MQTTMessage) -> None:
        try:
            text = msg.payload.decode("utf-8")
            payload_obj = json.loads(text) if text else {}
        except Exception:
            payload_obj = {"_raw": msg.payload.decode("utf-8", errors="replace")}

        event = MqttEvent(topic=msg.topic, payload=payload_obj, qos=msg.qos, retain=msg.retain)
        try:
            self.rx_queue.put_nowait(event)
        except queue.Full:
            pass

    def connect(self, timeout: float = 5.0) -> bool:
        self._connected_event.clear()
        self._client.connect(self.broker_host, self.broker_port, keepalive=self.keepalive)
        self._client.loop_start()
        return self._connected_event.wait(timeout=timeout)

    def disconnect(self) -> None:
        try:
            self._client.disconnect()
        finally:
            self._client.loop_stop()

    def subscribe(self, topics: List[Tuple[str, int]]) -> None:
        for topic, qos in topics:
            self._client.subscribe(topic, qos=qos)

    def publish_json(self, topic: str, payload: Dict[str, Any], qos: int = 0, retain: bool = False) -> None:
        data = json.dumps(payload, separators=(",", ":"), ensure_ascii=False)
        self._client.publish(topic, data, qos=qos, retain=retain)

    def get_rx(self, timeout: Optional[float] = None) -> Optional[MqttEvent]:
        try:
            return self.rx_queue.get(timeout=timeout)
        except queue.Empty:
            return None

    def is_connected(self) -> bool:
        return self._connected_event.is_set()
