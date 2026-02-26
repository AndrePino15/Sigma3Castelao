# Sigma3 Top-level Server (SafeGoals Topic Scheme + Web UI + MQTT + Telemetry + Stadium/Seat Preview)

This repository contains the **top-level server-side control software** for the Sigma3 stadium-seat prototype.

It provides:
- A **Web UI** (Flask) to send control commands to one or more *Sections* (e.g. A,B,C...).
- An **MQTT publisher** that sends:
  - `safegoals/section/<section_id>/control` (normal control)
  - `safegoals/section/<section_id>/led` (LED control)
  - `safegoals/emergency` (emergency override broadcast)
- An **MQTT telemetry subscriber** that reads:
  - `safegoals/section/+/status` (published by each Raspberry Pi section controller)
- A **2D Stadium Preview** (ellipse + wedges) **and a simple seat LED preview**:
  - When you press LED buttons, the browser immediately shows a “flashing / moving” effect.
  - This preview is a *software simulator* and does **not** require LEDs connected.

> ✅ This repo is designed to match the topic scheme suggested by the team:
> - **Per-section topics** for control and LED
> - **One emergency topic** all sections subscribe to
> - **Only status is subscribed by the server** (read-only topic)

---

## Repository structure (what each file does)

```
sigma3-server/
├─ run.py                         # Entry-point: starts the Flask app
├─ requirements.txt               # Python dependencies
├─ .env.example                   # Example environment variables (copy to .env)
├─ server/
│  ├─ __init__.py                 # create_app() factory
│  ├─ app.py                      # `python -m server.app` entry (alternative to run.py)
│  ├─ runtime_config.py           # Loads .env / environment variables into a config dataclass
│  ├─ mqtt_topics.py              # Topic scheme (SafeGoals): control/led/status/emergency
│  ├─ mqtt_client.py              # MQTT wrapper (connect, publish, subscribe)
│  ├─ messages.py                 # Message builders (JSON payloads)
│  ├─ state.py                    # In-memory state: last inputs + preview state + telemetry cache
│  ├─ ui.py                       # Flask blueprint routes (web UI endpoints)
│  └─ utils.py                    # Helpers (timestamps, parsing)
├─ templates/
│  └─ index.html                  # Web UI layout (forms + preview canvas)
└─ static/
   ├─ styles.css                  # UI styling
   └─ app.js                      # Stadium + seat preview renderer
```

---

## Quick start (macOS / Linux)

### 0) Prerequisites
- Python 3.9+ (works on 3.9; 3.10+ recommended)
- An MQTT broker reachable at `MQTT_HOST:MQTT_PORT`

### 1) Create venv + install deps
```bash
cd sigma3-server
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2) Start Mosquitto broker (choose ONE way)

**Option A — Run `mosquitto` in a terminal**
```bash
mosquitto -v
```
Keep this terminal open.

If you see **“Address already in use”**, it means a broker is already running on port 1883.
Find and stop it:
```bash
lsof -nP -iTCP:1883 -sTCP:LISTEN
kill <PID>
```

**Option B — Use Homebrew service (optional)**
Homebrew services sometimes fail on some macOS setups (launchctl errors).  
If `brew services start mosquitto` fails, just use Option A (manual `mosquitto -v`) — it’s totally fine.

### 3) Configure env
```bash
cp .env.example .env
```
Edit `.env` if needed (broker host, port, default sections, etc).

### 4) Run the server
Choose ONE:

**Option 1 (recommended):**
```bash
python3 run.py
```

**Option 2:**
```bash
python3 -m server.app
```

Open:
- http://127.0.0.1:5000

---

## Using the Web UI

### Multi-section sending
In each form, you can enter:
- `A` (single section), or
- `A,B` (multiple sections), or
- `A,B,C,D` (broadcast to many sections)

The server will publish to each section’s topic.

### Persisting inputs (no more “always default”)
This server stores your *last entered values* in memory (per-form) and re-renders them as the next defaults.
So if you set Section to `B` and change LED parameters, the page will keep those values after submit.

---

## MQTT topic scheme (SafeGoals)

### Publish (Server → Section Controller)
- Control: `safegoals/section/<section_id>/control`
- LED: `safegoals/section/<section_id>/led`
- Emergency broadcast: `safegoals/emergency`

### Subscribe (Section Controller → Server)
- Status / Telemetry: `safegoals/section/<section_id>/status`  
  Server subscribes to: `safegoals/section/+/status`

---

## Message payloads (high level)

All messages are JSON:
```json
{
  "type": "led",
  "ts_ms": 1234567890,
  "payload": { ... }
}
```

Examples:
- LED Mexican wave payload: direction, speed, width, hold_ms, RGB
- LED Sparkle payload: duration_ms, density, RGB
- Control payload: mode/goal/vote/animation_id, etc.

See `server/messages.py` for exact builders.

---

## Notes for real hardware (Pi 3B+ section controller)
This server only requires **MQTT** to be reachable.  
If the Pi is on the same Wi‑Fi:
- set `MQTT_HOST` in `.env` to the broker IP,
- ensure the Pi section controller subscribes to:
  - `safegoals/section/<section_id>/control`
  - `safegoals/section/<section_id>/led`
  - `safegoals/emergency`
and publishes status to:
  - `safegoals/section/<section_id>/status`

---

## Troubleshooting

### 1) `TemplateNotFound: index.html`
Make sure the folder layout is exactly:
- `templates/index.html` at the repo root  
and run from the repo root:
```bash
cd sigma3-server
python3 run.py
```

### 2) `ConnectionRefusedError` from MQTT
Broker is not running or wrong host/port.
- Start Mosquitto (Option A) and keep it open
- Check `.env` for `MQTT_HOST` and `MQTT_PORT`

### 3) Preview not lighting
The preview is driven by your **LED button clicks** (server broadcasts a preview event).  
It does NOT require real LEDs connected.

If the canvas shows only outlines, refresh the page and try an LED command again.

---

## License
MIT (see `LICENSE` if you add it)
