"""
CAN protocol helpers for the Section Controller.

Protocol assumptions for the current seat-node firmware:
- Node reply frames are received on arbitration id 0x100 (NODE_REPLY_ID)
- Node command frames are sent to per-node ids in the 0x200 + seat_id range
- Each TX frame contains two RGB subframes for the same LED
- Node displays subframe 1 immediately, then subframe 2 after ~50 ms
"""
from __future__ import annotations
from typing import Dict, Any, Iterable
import can
# ID ranges / protocol IDs
NODE_TO_HUB_BASE = 0x100
HUB_TO_NODE_BASE = 0x200
MAX_SEATS = 256

BROADCAST_CMD_ID = 0x400
EMERGENCY_ID = 0x000
NODE_REPLY_ID = 0x100

TX_FLAG_VOTE_REQUEST = 1 << 0
TX_FLAG_REPLY_REQUEST = 1 << 1

RX_FLAG_SOS = 1 << 0
RX_FLAG_OCCUPANCY = 1 << 1
RX_FLAG_VOTED = 1 << 2
RX_FLAG_VOTE = 1 << 3


def seat_cmd_id(seat: int) -> int:
    if not (0 <= seat <= MAX_SEATS):
        raise ValueError("seat out of range")
    return HUB_TO_NODE_BASE + seat

def seat_status_id(seat: int) -> int:
    if not (0 <= seat <= MAX_SEATS):
        raise ValueError("seat out of range")
    return NODE_TO_HUB_BASE + seat


def _rgb_triplet(rgb: Iterable[int]) -> list[int]:
    values = list(rgb)
    if len(values) != 3:
        raise ValueError("RGB triplet must have exactly 3 values")
    return [int(v) & 0xFF for v in values]


def encode_node_frame(
    node_id: int,
    rgb1: Iterable[int],
    rgb2: Iterable[int],
    *,
    vote_request: bool = False,
    reply_request: bool = False,
) -> can.Message:
    """
    Build the section-controller -> node CAN frame.

    Layout:
      data[0] bit0=vote_request, bit1=reply_request
      data[1] reserved
      data[2:5] = RGB subframe 1
      data[5:8] = RGB subframe 2
    """
    flags = 0
    if vote_request:
        flags |= TX_FLAG_VOTE_REQUEST
    if reply_request:
        flags |= TX_FLAG_REPLY_REQUEST

    c1 = _rgb_triplet(rgb1)
    c2 = _rgb_triplet(rgb2)
    data = [flags & 0xFF, 0, c1[0], c1[1], c1[2], c2[0], c2[1], c2[2]]
    return can.Message(arbitration_id=int(node_id), data=data, is_extended_id=False)

# this function isn't really used
def encode_led_set(
    seat: int,
    r: int,
    g: int,
    b: int,
    *,
    vote_request: bool = False,
    reply_request: bool = False,
) -> can.Message:
    """
    LEGACY: backwards-compatible helper used by the existing bridge LED path.

    This wraps the newer node-frame wire format and duplicates the same RGB
    into both subframes. Keep only for migration compatibility.
    """
    arb = seat_cmd_id(seat)
    # NOTE: keeping the seat-based helper name while using the new wire format
    # lets the current bridge LED command path remain functional during Phase 0.
    return encode_node_frame(
        arb,
        (r, g, b),
        (r, g, b),
        vote_request=vote_request,
        reply_request=reply_request,
    )


def decode(msg: can.Message) -> Dict[str, Any]:
    """
    Decodes node -> section-controller reply frames.

    Expected layout:
      arbitration_id = 0x100
      data[0] reserved
      data[1] bit0=sos bit1=occupancy bit2=voted bit3=vote
      data[2] node_id LSB
      data[3] top 3 bits = node_id MSBs (11-bit node_id total)
    """
    if msg.is_extended_id:
        raise ValueError("Received CAN message has an unexpected extended id.")
    if len(msg.data) < 4:
        raise ValueError("Received CAN message has a short CAN frame")
    if msg.arbitration_id != NODE_REPLY_ID:
        raise ValueError(f"Received CAN message has an unexpected reply arbitration id 0x{msg.arbitration_id:03X}")

    flags = int(msg.data[1]) & 0x0F
    # reconstruction of the node_id of the seat that sent the message
    node_id = (((int(msg.data[3]) >> 5) & 0x07) << 8) | (int(msg.data[2]) & 0xFF)
    seat = node_id - HUB_TO_NODE_BASE if HUB_TO_NODE_BASE <= node_id <= (HUB_TO_NODE_BASE + MAX_SEATS) else None

    out: Dict[str, Any] = {
        "direction": "node_to_hub_reply",
        "seat": seat,
        "node_id": node_id,
        "type": "NODE_REPLY",
        "raw_id": int(msg.arbitration_id),
        "data": list(msg.data),
        "sos": bool(flags & RX_FLAG_SOS),
        "occupied": bool(flags & RX_FLAG_OCCUPANCY),
        "voted": bool(flags & RX_FLAG_VOTED),
        "vote": bool(flags & RX_FLAG_VOTE) if (flags & RX_FLAG_VOTED) else None,
    }

    return out
