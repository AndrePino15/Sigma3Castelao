"""Sigma3 server package.

create_app() builds the Flask application, initializes MQTT client,
registers routes, and initializes RTP audio streamer.
"""

from flask import Flask
from .runtime_config import load_config
from .mqtt_client import MqttClient
from .ui import bp as ui_bp
from .audio_streamer import AudioStreamer

from .audio_rtp import AudioRtpConfig, RtpAudioStreamer


def create_app() -> Flask:
    app = Flask(__name__, template_folder="../templates", static_folder="../static")
    app.secret_key = "sigma3-dev-secret"

    cfg = load_config()
    app.config["SIGMA3_CFG"] = cfg

    mqttc = MqttClient(cfg)
    mqttc.start()
    app.config["SIGMA3_MQTT"] = mqttc

# Live audio streamer (server -> Pi RTP/UDP)
    audio = AudioStreamer(
        target_ip=cfg.audio_target_ip,
        target_port=cfg.audio_target_port,
        input_backend=cfg.audio_input_backend,
        input_device=cfg.audio_input_device,
        opus_bitrate=cfg.audio_opus_bitrate,
    )
    app.config["SIGMA3_AUDIO"] = audio
    
    app.register_blueprint(ui_bp)
    return app