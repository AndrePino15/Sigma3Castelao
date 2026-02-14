# Per-file guide (what each file does, how it is built, and how to modify it)

This document is intentionally **very detailed**, so that someone new to the repo can understand the system quickly.

## server/app.py
- Entry point when you run `python -m server.app`.
- Loads configuration (env vars), creates the Flask app, and starts the MQTT client thread.
- Registers routes from `server/routes.py`.
- Runs Flask dev server (or Waitress if you choose).

Modify when:
- You want to change how the app is started (host/port, production server).
- You want to initialise additional background services.

## server/config.py
- Central place to read environment variables.
- Defines defaults so the server runs even without a `.env`.

Modify when:
- You want different topic names or broker settings.
- You want to add new configuration values.

## server/mqtt_client.py
- Wraps `paho-mqtt`.
- Manages connection + reconnection.
- Provides:
  - `publish(topic, payload_dict)`
  - `start()` / `stop()`
- Subscribes to telemetry topic and passes messages to `server/state.py`.

Modify when:
- You want QoS changes, retained messages, TLS, etc.

## server/messages.py
- Defines **all message formats** the server uses.
- Each outgoing command has a builder function that returns a Python dict:
  - `build_mode_command(...)`
  - `build_goal_event(...)`
  - `build_vote_command(...)`
  - `build_animation_command(...)`
  - `build_led_command(...)`

Modify when:
- You want to change the JSON schema shared with the Raspberry Pi.

## server/state.py
- Keeps a small in-memory store of latest telemetry per section.
- Provides thread-safe read/write helpers.

Modify when:
- You want to persist telemetry to disk or a database.

## server/routes.py
- Contains Flask routes for the Web UI.
- Converts form inputs to message dicts using `server/messages.py`.
- Publishes them through `server/mqtt_client.py`.

Modify when:
- You add a new Web UI button/action.

## templates/index.html
- The UI page layout (Jinja2 template).
- Displays:
  - Current topics
  - Forms to send commands
  - Telemetry table

Modify when:
- You want to change layout, add new controls, or add live auto-refresh.

## static/styles.css
- Simple styling for clarity.

## static/app.js
- Optional client-side helpers.
- Current version is minimal to avoid complexity.

## scripts/*
- Convenience scripts to start dev environment (broker + server).
