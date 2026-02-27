from .base import AnimationProtocol
from .traveling_wave import TravelingWaveAnimation
from .sparkle import SparkleAnimation
from .pulse import PulseAnimation
from .chase import ChaseAnimation
from .wipe import WipeAnimation

_ANIMATIONS = {
    "traveling_wave": TravelingWaveAnimation(),
    "sparkle": SparkleAnimation(),
    "pulse": PulseAnimation(),
    "chase": ChaseAnimation(),
    "wipe": WipeAnimation(),
}


def get_animation(animation_id: str) -> AnimationProtocol:
    """Return the animation implementation for the provided animation_id."""
    return _ANIMATIONS.get(str(animation_id), _ANIMATIONS["sparkle"])
