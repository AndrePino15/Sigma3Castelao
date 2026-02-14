"""App entry point.

Run:
    python -m server.app

What happens:
1) Loads configuration from env vars (see server/config.py and .env.example)
2) Starts MQTT background client
3) Starts Flask Web UI

This file intentionally stays small; most logic lives in:
- server/routes.py (UI actions)
- server/messages.py (schemas)
- server/mqtt_client.py (broker I/O)
"""

from __future__ import annotations

import logging

from flask import Flask
from waitress import serve

from .config import load_config
from .mqtt_client import MqttClient
from .routes import bp


def create_app() -> Flask:
    cfg = load_config()

    app = Flask(__name__, template_folder="../templates", static_folder="../static")
    app.secret_key = cfg.flask_secret_key

    # Store config + mqtt client on app for easy access in routes
    app.config["SIGMA3_CFG"] = cfg

    mqttc = MqttClient(cfg)
    mqttc.start()
    app.config["SIGMA3_MQTT"] = mqttc

    app.register_blueprint(bp)
    return app


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    app = create_app()
    cfg = app.config["SIGMA3_CFG"]

    # Dev server (Flask) is okay for coursework demos.
    # For a more stable demo, use waitress.
    use_waitress = False

    if use_waitress:
        serve(app, host=cfg.flask_host, port=cfg.flask_port)
    else:
        app.run(host=cfg.flask_host, port=cfg.flask_port, debug=True)


if __name__ == "__main__":
    main()
