# Screen Module MQTT Protocol (Qt GUI)

## Overview
This document defines MQTT topics and JSON payloads between:
- Screen GUI (`qt_gui.py`)
- Fake/real backend server (`fake_server.py` or production service)

Target display:
- Raspberry Pi Touch Display 2 (720x1280) or desktop equivalent

## Broker
- Host: `127.0.0.1` (demo)
- Port: `1883`
- Auth: none (demo only)
- Keepalive: `60s`

## Identity
- Seat/device id example: `A3-12`
- Client id suggestion:
  - GUI: `qt_gui_<seat_id>`
  - Server: `fake_server_<seat_id>` or backend-defined id

## Topics

### 1) Telemetry (Server -> Screen)
- Topic: `stadium/seat/<seat_id>/telemetry`
- Direction: downlink
- QoS: `0`
- Retain: `false`
- Purpose: real-time dashboard/status fields

Example:
```json
{
  "ts": 1700000000.0,
  "mode": "RUN",
  "device_id": "A3-12",
  "rssi": -55,
  "metric": 0.72,
  "msg": "Match: TeamA vs TeamB"
}
```

### 2) Command (Screen -> Server)
- Topic: `stadium/seat/<seat_id>/cmd`
- Direction: uplink
- QoS: `1`
- Retain: `false`
- Purpose: send user actions (order, safety ack, etc.)

Example:
```json
{
  "ts": 1700000000.0,
  "device_id": "A3-12",
  "cmd": "ORDER",
  "value": 1,
  "payload": {
    "item": "Cola",
    "qty": 2,
    "note": "no ice"
  }
}
```

### 3) ACK (Server -> Screen)
- Topic: `stadium/seat/<seat_id>/ack`
- Direction: downlink
- QoS: `1`
- Retain: `false`
- Purpose: acknowledge commands from GUI

Example:
```json
{
  "ts": 1700000001.0,
  "ok": true,
  "ref_cmd": "ORDER",
  "msg": "ACK for ORDER"
}
```

### 4) Safety Broadcast (Server -> Screen)
- Topic: `stadium/broadcast/safety`
- Direction: downlink broadcast
- QoS: `1`
- Retain: `true` (recommended)
- Purpose: force Safety UI mode and clear it

Safety example:
```json
{
  "ts": 1700000100.0,
  "mode": "SAFETY",
  "level": "CRITICAL",
  "msg": "Evacuate via Exit B"
}
```

Clear example:
```json
{
  "ts": 1700000200.0,
  "mode": "NORMAL",
  "level": "INFO",
  "msg": "Safety cleared"
}
```

