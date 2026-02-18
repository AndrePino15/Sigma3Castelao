from __future__ import annotations
import logging
from flask import Flask
from .config import load_config
from .mqtt_client import MqttClient
from .routes import bp

def create_app() -> Flask:
    cfg = load_config()
    app = Flask(__name__, template_folder="../templates", static_folder="../static")
    app.secret_key = cfg.flask_secret_key
    app.config["SIGMA3_CFG"] = cfg

    mqttc = MqttClient(cfg)
    mqttc.start()
    app.config["SIGMA3_MQTT"] = mqttc

    app.register_blueprint(bp)
    return app

def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    app = create_app()
    cfg = app.config["SIGMA3_CFG"]
    app.run(host=cfg.flask_host, port=cfg.flask_port, debug=True)

if __name__ == "__main__":
    main()
