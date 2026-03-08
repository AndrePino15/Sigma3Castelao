from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Dict, List

import can

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.bridge import Bridge  # noqa: E402
from app.mqtt_client import MqttEvent  # noqa: E402
from app.mqtt_topics import control_topic, led_topic  # noqa: E402
import canbus.protocol as protocol  # noqa: E402


class FakeMqtt:
    """Minimal MQTT stub that records publishes and always reports connected."""

    def __init__(self) -> None:
        """Initialize publish capture list."""
        self.published: List[tuple[str, Dict[str, Any], int, bool]] = []

    def is_connected(self) -> bool:
        """Return a connected state for unit tests."""
        return True

    def publish_json(self, topic: str, payload: Dict[str, Any], qos: int = 0, retain: bool = False) -> None:
        """Capture one publish call."""
        self.published.append((topic, payload, qos, retain))


class FakeCan:
    """Minimal CAN transport stub that captures outbound messages."""

    def __init__(self) -> None:
        """Initialize outbound CAN capture list."""
        self.sent: List[can.Message] = []

    def send(self, msg: can.Message) -> None:
        """Capture one outbound CAN frame."""
        self.sent.append(msg)


def test_vote_request_control_to_can_and_vote_reply_to_mqtt():
    """Round-trip vote flow from control-topic request to CAN and back to MQTT."""
    section_id = 1
    bridge = Bridge(section_id=section_id, broker_host="127.0.0.1")
    bridge.mqtt = FakeMqtt()  # type: ignore[assignment]
    bridge.can = FakeCan()  # type: ignore[assignment]
    bridge._can_available = True

    # 1) Simulate control-topic vote request from server.
    vote_event = MqttEvent(
        topic=control_topic(section_id),
        ts_ms=0,
        payload={"type": "vote", "payload": {"vote_id": "v1", "duration_s": 20}},
    )
    bridge.mqtt_handle(vote_event)
    assert bridge._vote_request_sweep_pending is True

    # 2) Simulate an LED update to trigger outbound node CAN frame creation.
    led_event = MqttEvent(
        topic=led_topic(section_id),
        ts_ms=1,
        payload={"seat": 4, "rgb": [10, 20, 30]},
    )
    bridge.mqtt_handle(led_event)

    assert len(bridge.can.sent) == 1  # type: ignore[union-attr]
    tx_msg = bridge.can.sent[0]  # type: ignore[union-attr]
    assert tx_msg.arbitration_id == protocol.HUB_TO_NODE_BASE + 4
    assert (int(tx_msg.data[0]) & protocol.TX_FLAG_VOTE_REQUEST) != 0

    # 3) Simulate node reply containing "voted=yes" and propagate to MQTT.
    node_id = protocol.HUB_TO_NODE_BASE + 4
    data3 = ((node_id >> 8) & 0x07) << 5
    rx_msg = can.Message(
        arbitration_id=protocol.NODE_REPLY_ID,
        data=[0, 0b1100, node_id & 0xFF, data3, 0, 0, 0, 0],  # voted=1, vote=1
        is_extended_id=False,
    )
    bridge.can_handle(rx_msg)

    assert len(bridge.mqtt.published) == 1  # type: ignore[union-attr]
    topic, payload, _, _ = bridge.mqtt.published[0]  # type: ignore[union-attr]
    assert topic == f"safegoals/section/{section_id}/status"
    assert payload["type"] == "seat_event"
    assert payload["section"] == section_id
    assert payload["seat_id"] == 4
    assert payload["node_id"] == node_id
    assert payload["voted"] is True
    assert payload["vote"] is True

