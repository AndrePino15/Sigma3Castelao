"""Sigma3 Server package.

This package is structured so that:
- `server/app.py` starts the Flask UI and MQTT background client.
- Message formats live in `server/messages.py` (single source of truth).
- Latest telemetry lives in `server/state.py` (thread-safe in-memory store).
"""
