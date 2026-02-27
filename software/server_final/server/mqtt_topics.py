"""MQTT topic scheme helpers.

Example:
  - safegoals/section/<section_id>/control
  - safegoals/section/<section_id>/led
  - safegoals/section/<section_id>/status
  - safegoals/emergency

Also includes screen-side topics used by qt_gui.py:
  - stadium/seat/<seat_id>/ack
  - stadium/broadcast/safety
  - stadium/broadcast/vote
  - stadium/broadcast/replay
  - stadium/config/fixture_id
"""
ROOT = "safegoals"
SCREEN_ROOT = "stadium"

def section_root(section_id: str) -> str:
    return f"{ROOT}/section/{section_id}"

def emergency_topic() -> str:
    return f"{ROOT}/emergency"

def show_clock_topic() -> str:
    return f"{ROOT}/show/clock"

def control_topic(section_id: str) -> str:
    return f"{section_root(section_id)}/control"

def led_topic(section_id: str) -> str:
    return f"{section_root(section_id)}/led"

def status_topic(section_id: str) -> str:
    return f"{section_root(section_id)}/status"

def status_wildcard() -> str:
    return f"{ROOT}/section/+/status"


def screen_ack_topic(seat_id: str) -> str:
    return f"{SCREEN_ROOT}/seat/{seat_id}/ack"


def screen_safety_topic() -> str:
    return f"{SCREEN_ROOT}/broadcast/safety"


def screen_vote_topic() -> str:
    return f"{SCREEN_ROOT}/broadcast/vote"


def screen_replay_topic() -> str:
    return f"{SCREEN_ROOT}/broadcast/replay"


def screen_fixture_topic() -> str:
    return f"{SCREEN_ROOT}/config/fixture_id"


def screen_cmd_wildcard() -> str:
    return f"{SCREEN_ROOT}/seat/+/cmd"
