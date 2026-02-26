"""Module entry point.

Allows running:
    python3 -m server.app
"""
from . import create_app

app = create_app()

def main():
    app.run(host=app.config["SIGMA3_CFG"].flask_host, port=app.config["SIGMA3_CFG"].flask_port, debug=True)

if __name__ == "__main__":
    main()
