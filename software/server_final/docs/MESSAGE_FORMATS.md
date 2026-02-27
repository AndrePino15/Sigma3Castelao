# Message formats (JSON)

## LED (pattern-level)
```json
{
  "type": "led",
  "ts_ms": 1700000000000,
  "payload": {
    "pattern": "mexican_wave",
    "direction": "left_to_right",
    "speed_seats_per_s": 12,
    "width_seats": 3,
    "hold_ms": 120,
    "color": {"r": 0, "g": 120, "b": 255},
    "background": {"r": 0, "g": 0, "b": 0}
  }
}
```

> This is NOT pixel-level. The Pi/seat firmware maps it to actual LED indices.
The preview uses the same fields to simulate a stadium-wide effect.
