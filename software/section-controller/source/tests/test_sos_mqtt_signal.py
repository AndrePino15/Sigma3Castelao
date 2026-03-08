from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Dict, List

import can

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.bridge import Bridge  # noqa: E402
import canbus.protocol as protocol  # noqa: E402


class FakeMqtt:
    """Minimal MQTT stub that records published payloads for assertions."""

    def __init__(self) -> None:
        """Initialize an in-memory list for published events."""
        self.published: List[tuple[str, Dict[str, Any], int, bool]] = []

    def is_connected(self) -> bool:
        """Pretend the MQTT connection is always up for this unit test."""
        return True

    def publish_json(self, topic: str, payload: Dict[str, Any], qos: int = 0, retain: bool = False) -> None:
        """Capture each publish call."""
        self.published.append((topic, payload, qos, retain))


def test_can_sos_bit_publishes_mqtt_seat_event():
    """Set SOS bit in a synthetic CAN reply and verify MQTT seat_event payload."""
    bridge = Bridge(section_id=1, broker_host="127.0.0.1")
    bridge.mqtt = FakeMqtt()  # type: ignore[assignment]

    node_id = protocol.HUB_TO_NODE_BASE + 4  # expected seat_id = 4
    data3 = ((node_id >> 8) & 0x07) << 5
    # data[1]: bit0=sos, bit1=occupancy, bit2=voted, bit3=vote
    msg = can.Message(
        arbitration_id=protocol.NODE_REPLY_ID,
        data=[0, 0b0001, node_id & 0xFF, data3, 0, 0, 0, 0],
        is_extended_id=False,
    )

    bridge.can_handle(msg)

    assert len(bridge.mqtt.published) == 1  # type: ignore[union-attr]
    topic, payload, _, _ = bridge.mqtt.published[0]  # type: ignore[union-attr]
    assert topic == "safegoals/section/1/status"
    assert payload["type"] == "seat_event"
    assert payload["section"] == 1
    assert payload["node_id"] == node_id
    assert payload["seat_id"] == 4
    assert payload["sos"] is True
    assert payload["occupied"] is False
    assert payload["voted"] is False
    assert payload["vote"] is None
    # Seat SOS should not force global SAFETY mode.
    assert bridge.mode.name == "NORMAL"

