"""Runtime configuration loader (env + .env)."""

from dataclasses import dataclass
import os
from dotenv import load_dotenv


@dataclass
class RuntimeConfig:
    mqtt_host: str
    mqtt_port: int

    # UI defaults
    default_sections: str          # e.g. "1" or "1,2"
    all_sections: str              # e.g. "1,2,3,4,5,6,7,8,9,10" (used when user types ALL)

    # Flask bind
    flask_host: str
    flask_port: int

    # Audio RTP defaults
    audio_target_ip: str
    audio_target_port: int
    audio_input_backend: str
    audio_input_device: str
    audio_opus_bitrate: str
    show_clock_period_ms: int
    cue_start_lead_ms: int



def load_config() -> RuntimeConfig:
    # Load .env from the current working directory (project root)
    load_dotenv(override=False)

    mqtt_host = os.getenv("MQTT_HOST", "127.0.0.1")
    mqtt_port = int(os.getenv("MQTT_PORT", "1883"))

    default_sections = os.getenv("DEFAULT_SECTIONS", "1")

    # NEW: list used to expand user input "ALL"
    # Keep it as CSV string here; routes/utils can parse it into a list.
    all_sections = os.getenv("ALL_SECTIONS", "1,2,3,4,5,6,7,8,9,10")

    flask_host = os.getenv("FLASK_HOST", "127.0.0.1")
    flask_port = int(os.getenv("FLASK_PORT", "5000"))

    audio_target_ip = os.getenv("AUDIO_TARGET_IP", "127.0.0.1")
    audio_target_port = int(os.getenv("AUDIO_TARGET_PORT", "5004"))

     # Input settings (server machine microphone)
    audio_input_backend = os.getenv("AUDIO_INPUT_BACKEND", "")
    audio_input_device = os.getenv("AUDIO_INPUT_DEVICE", "")
    audio_opus_bitrate = os.getenv("AUDIO_OPUS_BITRATE", "64k")
    show_clock_period_ms = int(os.getenv("SHOW_CLOCK_PERIOD_MS", "1000"))
    cue_start_lead_ms = int(os.getenv("CUE_START_LEAD_MS", "500"))

    return RuntimeConfig(
        mqtt_host=mqtt_host,
        mqtt_port=mqtt_port,
        default_sections=default_sections,
        all_sections=all_sections,
        flask_host=flask_host,
        flask_port=flask_port,
        audio_target_ip=audio_target_ip,
        audio_target_port=audio_target_port,
        audio_input_backend=audio_input_backend,
        audio_input_device=audio_input_device,
        audio_opus_bitrate=audio_opus_bitrate,
        show_clock_period_ms=show_clock_period_ms,
        cue_start_lead_ms=cue_start_lead_ms,
    )
