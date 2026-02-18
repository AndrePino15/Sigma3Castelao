from __future__ import annotations
from dataclasses import dataclass
from typing import Optional, Dict, Any, Tuple
import can
from .types import MessageTypes

# ID ranges (example)   
SEAT_TO_CTRL_BASE = 0x200
HUB_TO_NODE_BASE = 0x100
MAX_SEATS = 256

BROADCAST_CMD_ID = 0x400
EMERGENCY_ID = 0x000


def seat_cmd_id(seat: int) -> int:
    if not (0 <= seat <= MAX_SEATS):
        raise ValueError("seat out of range")
    return HUB_TO_NODE_BASE + seat

def seat_status_id(seat: int) -> int:
    if not (0 <= seat <= MAX_SEATS):
        raise ValueError("seat out of range")
    return SEAT_TO_CTRL_BASE + seat


def encode_led_set(seat: int, r: int, g: int, b: int) -> can.Message:
    arb = seat_cmd_id(seat)
    # the bitwise & operation makes sure that the input RGB values are only 8 bit, discarding anything bigger than 
    data = [MessageTypes.LED_SET, r & 0xFF, g & 0xFF, b & 0xFF, 0, 0, 0, 0]
    return can.Message(arbitration_id=arb, data=data, is_extended_id=False)


def decode(msg: can.Message) -> Dict[str, Any]:
    """
    Decodes a raw CAN message into a dict.
    Assumes msg.data[0] is MessageTypes.
    """
    if msg.is_extended_id:
        raise ValueError("unexpected extended id")

    msg_type = MessageTypes(msg.data[0])

    # infer seat from arbitration_id range
    if SEAT_TO_CTRL_BASE <= msg.arbitration_id <= SEAT_TO_CTRL_BASE + MAX_SEATS:
        seat = msg.arbitration_id - SEAT_TO_CTRL_BASE
        direction = "seat_to_ctrl"
    elif HUB_TO_NODE_BASE <= msg.arbitration_id <= HUB_TO_NODE_BASE + MAX_SEATS:
        seat = msg.arbitration_id - HUB_TO_NODE_BASE
        direction = "ctrl_to_seat"
    else:
        seat = None
        direction = "other"

    out: Dict[str, Any] = {
        "direction": direction,
        "seat": seat,
        "type": msg_type.name,
        "raw_id": msg.arbitration_id,
        "data": list(msg.data),
    }

    # add typed parsing for a few messages
    if msg_type == MessageTypes.OCCUPANCY:
        out["occupied"] = bool(msg.data[1])
    elif msg_type == MessageTypes.HEARTBEAT:
        out["uptime_s"] = int.from_bytes(bytes(msg.data[1:5]), "big", signed=False)

    return out
