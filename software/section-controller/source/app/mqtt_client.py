'''
    This file will provide functionality to connect cleanly to the MQTT server and make it easy to connect,
    subscribe and publish into the MQTT broker.
'''
from __future__ import annotations

import json
import queue
import threading
import time
from dataclasses import dataclass
from typing import Any, Dict, Optional, List, Tuple
import logging

import paho.mqtt.client as mqtt

LOGGER = logging.getLogger(__name__)

# the frozen parameter is set because we don't want to modify a received message. We use it as is to not change its content
@dataclass(frozen=True)
class MqttEvent:
    topic: str
    payload: Dict[str, Any]
    qos: int = 0
    retain: bool = False


class MqttClient:
    """
    Thin wrapper around paho-mqtt.
    - Keeps callbacks lightweight by pushing received messages to a queue.
    - Application/bridge consumes the queue and performs heavier logic.
    """

    def __init__(
        self,
        broker_host: str,
        broker_port: int = 1883,
        client_id: Optional[str] = None,
        username: Optional[str] = None,
        password: Optional[str] = None,
        keepalive: int = 60,
        rx_maxsize: int = 0,  # 0 = infinite
    ) -> None:
        self.broker_host: int = broker_host
        self.broker_port: int = broker_port
        self.keepalive: int = keepalive     # this is the interval that the client will ping the broker to keep the connection alive

        self.rx_queue: "queue.Queue[MqttEvent]" = queue.Queue(maxsize=rx_maxsize)

        self._connected_event = threading.Event()
        self._stop_event = threading.Event()

        ''' Creation of the actual MQTT client using the paho.mqtt library. 
            clean_session=True just means that if there is a disconenction the broker won't remember the client, so the
        client subscribes fresh each time. '''
        self._client = mqtt.Client(client_id=client_id, clean_session=True)

        if username is not None:
            self._client.username_pw_set(username=username, password=password)

        # Callbacks. These are automaticallly called by paho when their respective network event happens
        self._client.on_connect = self._on_connect
        self._client.on_disconnect = self._on_disconnect
        self._client.on_message = self._on_message

        # lets paho handle reconnect delays. Waits between 1 and 10 seconds for reconnection attempts
        self._client.reconnect_delay_set(min_delay=1, max_delay=10)

    # ---------- Callbacks Section ----------

    def _on_connect(self, client: mqtt.Client, userdata: Any, flags: Dict[str, Any], rc: int) -> None:
        # rc == 0 means success
        if rc == 0:
            self._connected_event.set()
        else:
            self._connected_event.clear()

    def _on_disconnect(self, client: mqtt.Client, userdata: Any, rc: int) -> None:
        self._connected_event.clear()
        # paho can auto-reconnect if loop is running; we just mark disconnected.

    # Most important callback
    def _on_message(self, client: mqtt.Client, userdata: Any, msg: mqtt.MQTTMessage) -> None:
        # Decode payload safely to avoid heavy work here
        try:
            text = msg.payload.decode("utf-8")
            payload_obj = json.loads(text) if text else {}
        except Exception:
            # If it isn't JSON, we still forward something useful
            payload_obj = {"_raw": msg.payload.decode("utf-8", errors="replace")}

        event = MqttEvent(topic=msg.topic, payload=payload_obj, qos=msg.qos, retain=msg.retain)

        try:
            self.rx_queue.put_nowait(event)
        except queue.Full:
            # Overload policy: drop newest.
            # Later add counters/logging if needed.
            pass

    # ---------- Public API ----------

    def connect(self, timeout: float = 5.0) -> bool:
        """
        Connect and start the network loop in the background.
        Returns True if connected within timeout.
        """
        self._stop_event.clear()
        self._connected_event.clear()

        print(f"[DEBUG] broker_host={self.broker_host!r} ({type(self.broker_host)}), "
                f"broker_port={self.broker_port!r} ({type(self.broker_port)})")

        # connect() is non-blocking-ish, but actual connection is handled by loop_start()
        self._client.connect(self.broker_host, self.broker_port, keepalive=self.keepalive)
        self._client.loop_start()

        return self._connected_event.wait(timeout=timeout)

    def disconnect(self) -> None:
        """ Stop network loop and disconnect cleanly"""
        self._stop_event.set()
        try:
            self._client.disconnect()
        finally:
            self._client.loop_stop()

    def subscribe(self, topics: List[Tuple[str, int]]) -> None:
        """
        topics: list of (topic, qos)
        Example: [("safegoals/section/3/control/#", 0)]
        """
        for t, qos in topics:
            self._client.subscribe(t, qos=qos)
            LOGGER.info("Successfuly subscribed to %s.", t)

    def publish_json(self, topic: str, payload: Dict[str, Any], qos: int = 0, retain: bool = False) -> None:
        data = json.dumps(payload, separators=(",", ":"), ensure_ascii=False)
        self._client.publish(topic, data, qos=qos, retain=retain)

    def get_rx(self, timeout: Optional[float] = None) -> Optional[MqttEvent]:
        """
        Blocking read from RX queue. Returns None on timeout.
        """
        try:
            return self.rx_queue.get(timeout=timeout)
        except queue.Empty:
            return None

    def is_connected(self) -> bool:
        return self._connected_event.is_set()
