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
import canbus.protocol as protocol  # noqa: E402


class FakeMqtt:
    """Minimal MQTT stub capturing publishes for bridge unit tests."""

    def __init__(self) -> None:
        """Initialize an in-memory list of published messages."""

        self.published: List[tuple[str, Dict[str, Any], int, bool]] = []

    def is_connected(self) -> bool:
        """Pretend the MQTT client is always connected."""

        return True

    def publish_json(self, topic: str, payload: Dict[str, Any], qos: int = 0, retain: bool = False) -> None:
        """Record publish calls for assertions."""

        self.published.append((topic, payload, qos, retain))


def _bridge() -> Bridge:
    """Create a bridge instance with a fake MQTT transport."""

    b = Bridge(section_id=3, broker_host="127.0.0.1")
    b.mqtt = FakeMqtt()  # type: ignore[assignment]
    return b


def test_wrapped_vote_arms_vote_sweep():
    """Wrapped vote command should arm the next vote-request sweep."""

    b = _bridge()
    event = MqttEvent(topic=f"safegoals/section/{b.section_id}/control", ts_ms=0, payload={"type": "vote", "payload": {"vote_id": "v1"}})
    b.mqtt_handle(event)
    assert b._vote_request_sweep_pending is True


def test_wrapped_mode_updates_mode():
    """Wrapped mode command should update bridge operation mode."""

    b = _bridge()
    event = MqttEvent(topic=f"safegoals/section/{b.section_id}/control", ts_ms=0, payload={"type": "mode", "payload": {"mode": "SAFETY"}})
    b.mqtt_handle(event)
    assert b.mode.name == "SAFETY"


def test_can_handle_publishes_seat_event():
    """Decoded CAN replies should publish normalized seat_event payloads."""

    b = _bridge()
    node_id = protocol.HUB_TO_NODE_BASE + 7
    data3 = ((node_id >> 8) & 0x07) << 5
    msg = can.Message(
        arbitration_id=protocol.NODE_REPLY_ID,
        data=[0, 0b0110, node_id & 0xFF, data3, 0, 0, 0, 0],
        is_extended_id=False,
    )
    b.can_handle(msg)
    assert len(b.mqtt.published) == 1  # type: ignore[union-attr]
    topic, payload, _, _ = b.mqtt.published[0]  # type: ignore[union-attr]
    assert topic.endswith("/status")
    assert payload["type"] == "seat_event"
    assert payload["seat_id"] == 7
    assert payload["occupied"] is True
    assert payload["voted"] is True
