'''
    This section defines all topics used for the MQTT protocol. 
    We are going to have a topic per section and under that topic both control and LED topics.
    We will have a general emergency topic that all sections subscribe so that emergency resposne is immediate
for everyone. 
Example:
    - safegoals/section/<section_id>/control
    - safegoals/section/<section_id>/led
    - safegoals/emergency
'''

ROOT = "safegoals"

# Example:
# safegoals/section/3/control/led
# safegoals/section/3/status/seat/12

def section_root(section_id: int) -> str:
    return f"{ROOT}/section/{section_id}"

def emergency_topic() -> str:
    return f"{ROOT}/emergency"

def show_clock_topic() -> str:
    return f"{ROOT}/show/clock"

def control_topic(section_id: int) -> str:
    return f"{section_root(section_id)}/control"

def led_topic(section_id: int) -> str:
    return f"{section_root(section_id)}/led"

def status_topic(section_id: int) -> str:
    return f"{section_root(section_id)}/status"
