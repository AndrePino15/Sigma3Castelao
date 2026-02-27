from __future__ import annotations

import sys
from pathlib import Path

import can

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from canbus import protocol  # noqa: E402


def test_encode_node_frame_layout():
    """Verify node-frame packing order for flags and both RGB subframes."""

    msg = protocol.encode_node_frame(
        node_id=0x2A5,
        rgb1=(1, 2, 3),
        rgb2=(4, 5, 6),
        vote_request=True,
        reply_request=True,
    )
    assert msg.arbitration_id == 0x2A5
    assert list(msg.data) == [0b11, 0, 1, 2, 3, 4, 5, 6]


def test_decode_node_reply_layout():
    """Verify node reply decoding for node_id reconstruction and status flags."""

    node_id = 0x2A5
    data3 = ((node_id >> 8) & 0x07) << 5
    msg = can.Message(
        arbitration_id=protocol.NODE_REPLY_ID,
        data=[0, 0b1111, node_id & 0xFF, data3, 0, 0, 0, 0],
        is_extended_id=False,
    )
    decoded = protocol.decode(msg)
    assert decoded["node_id"] == node_id
    assert decoded["seat"] == node_id - protocol.HUB_TO_NODE_BASE
    assert decoded["sos"] is True
    assert decoded["occupied"] is True
    assert decoded["voted"] is True
    assert decoded["vote"] is True
