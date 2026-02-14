# Message formats (JSON schemas)

All messages are JSON objects. There are two directions:

- **Control** messages: Server → Pi
- **Telemetry** messages: Pi → Server

## 1) Control messages

Every control message has:

- `type`: string
- `ts_ms`: integer (Unix time in milliseconds)
- `payload`: object (depends on type)

### 1.1 Mode command
```json
{
  "type": "mode",
  "ts_ms": 1700000000000,
  "payload": {
    "mode": "normal",
    "reason": ""
  }
}
```
`mode` can be `normal` or `safety`.

### 1.2 Goal event
```json
{
  "type": "goal",
  "ts_ms": 1700000000000,
  "payload": {
    "team": "home"
  }
}
```
`team` can be `home` or `away`.

### 1.3 Vote command
```json
{
  "type": "vote",
  "ts_ms": 1700000000000,
  "payload": {
    "vote_id": "v1",
    "duration_s": 20,
    "options": ["yes", "no"],
    "one_vote_per_seat": true,
    "auto_close": true
  }
}
```

### 1.4 Animation command (media playback on Pi)
```json
{
  "type": "animation",
  "ts_ms": 1700000000000,
  "payload": {
    "animation_id": "goal_home",
    "duration_s": 3.0
  }
}
```

### 1.5 LED command (lighting pattern control)
```json
{
  "type": "led",
  "ts_ms": 1700000000000,
  "payload": {
    "pattern": "mexican_wave",
    "direction": "left_to_right",
    "speed_seats_per_s": 10,
    "width_seats": 3,
    "hold_ms": 120,
    "color": {"r": 0, "g": 120, "b": 255},
    "background": {"r": 0, "g": 0, "b": 0}
  }
}
```

**Note:** The Pi/seat firmware decides how to interpret the pattern and map it to physical LED indices.

---

## 2) Telemetry messages

The server expects telemetry like:

```json
{
  "section_id": "A",
  "ts_ms": 1700000000000,
  "heartbeat": true,
  "occupancy": 12,
  "votes": {"v1": {"yes": 7, "no": 3}},
  "alerts": ["over_occupancy_warning"]
}
```

Minimum recommended fields:
- `section_id`
- `ts_ms`
- `heartbeat`
