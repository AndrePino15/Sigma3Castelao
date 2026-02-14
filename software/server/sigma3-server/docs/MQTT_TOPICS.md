# MQTT Topics

This server uses two main topic patterns.

## 1) Control (Server → Section Controller)

Format:

`stadium/section/{section_id}/control`

Example:
- `stadium/section/A/control`
- `stadium/section/B/control`

Payload is JSON. See `docs/MESSAGE_FORMATS.md`.

---

## 2) Telemetry (Section Controller → Server)

Server subscribes to:

`stadium/section/+/telemetry`

Example published by the Pi:
- `stadium/section/A/telemetry`
- `stadium/section/B/telemetry`

---

## Why this pattern?
- It keeps messages **scoped by section**.
- Wildcard subscription lets the server monitor all sections.
- It scales well if you add more section controllers.
