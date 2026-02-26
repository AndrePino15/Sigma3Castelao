"""MQTT topic scheme (SafeGoals), matching the team's proposal.

Example:
  - safegoals/section/<section_id>/control
  - safegoals/section/<section_id>/led
  - safegoals/section/<section_id>/status
  - safegoals/emergency
"""
ROOT = "safegoals"

def section_root(section_id: str) -> str:
    return f"{ROOT}/section/{section_id}"

def emergency_topic() -> str:
    return f"{ROOT}/emergency"

def control_topic(section_id: str) -> str:
    return f"{section_root(section_id)}/control"

def led_topic(section_id: str) -> str:
    return f"{section_root(section_id)}/led"

def status_topic(section_id: str) -> str:
    return f"{section_root(section_id)}/status"

def status_wildcard() -> str:
    return f"{ROOT}/section/+/status"
