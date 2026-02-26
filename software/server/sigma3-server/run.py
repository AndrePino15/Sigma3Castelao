"""Run the Sigma3 top-level server (Flask + MQTT).

Usage:
    python3 run.py
"""
from server import create_app

app = create_app()

if __name__ == "__main__":
    app.run(host=app.config["SIGMA3_CFG"].flask_host, port=app.config["SIGMA3_CFG"].flask_port, debug=True)
