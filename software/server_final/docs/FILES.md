# Per-file guide (what each file does)

## server/app.py
Entry point (run with `python -m server.app`):
- loads config
- starts MQTT background client
- registers routes
- starts Flask

## server/routes.py
HTTP endpoints for the Web UI:
- reads form fields
- builds message dicts (using `server/messages.py`)
- publishes MQTT messages (via `server/mqtt_client.py`)
- updates **preview state** (last LED command) for the 2D simulator

## server/messages.py
Single source of truth for JSON schemas:
- mode / goal / vote / animation / led

## server/mqtt_client.py
MQTT wrapper (paho-mqtt):
- connects/reconnects
- publishes control messages
- subscribes to telemetry and updates `server/state.py`

## server/state.py
In-memory state:
- latest telemetry per section
- **latest preview LED command** (+ timestamp)

## templates/index.html
The Web UI page, including:
- Control forms
- Section Status table
- Stadium Preview canvas

## static/app.js
Front-end simulator:
- draws an ellipse stadium
- renders LED patterns (Mexican wave, sparkle)
- polls `/api/preview/command` to stay in sync with server actions
