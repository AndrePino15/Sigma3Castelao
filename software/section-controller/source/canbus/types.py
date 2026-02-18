from enum import IntEnum, Enum, auto

class MessageTypes (IntEnum):
    LED_SET = 0x01
    LED_MODE = 0x02
    OCCUPANCY = 0x10
    HEARTBEAT = 0x11
    EMERGENCY = 0x20

class OperationMode(Enum):
    NORMAL = auto()
    SAFETY = auto()
    ID_ASSIGNMENT = auto()
    DEGRADED = auto()
