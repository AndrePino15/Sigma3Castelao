from __future__ import annotations
import os
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()

@dataclass(frozen=True)
class Config:
    mqtt_host: str = os.getenv("MQTT_HOST", "localhost")
    mqtt_port: int = int(os.getenv("MQTT_PORT", "1883") or 1883)
    mqtt_username: str = os.getenv("MQTT_USERNAME", "")
    mqtt_password: str = os.getenv("MQTT_PASSWORD", "")
    mqtt_control_topic_fmt: str = os.getenv("MQTT_CONTROL_TOPIC_FMT", "stadium/section/{section_id}/control")
    mqtt_telemetry_topic: str = os.getenv("MQTT_TELEMETRY_TOPIC", "stadium/section/+/telemetry")
    default_section_id: str = os.getenv("DEFAULT_SECTION_ID", "A")
    flask_host: str = os.getenv("FLASK_HOST", "127.0.0.1")
    flask_port: int = int(os.getenv("FLASK_PORT", "5000") or 5000)
    flask_secret_key: str = os.getenv("FLASK_SECRET_KEY", "dev-secret-change-me")

def load_config() -> Config:
    return Config()
