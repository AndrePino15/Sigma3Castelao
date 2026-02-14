# Sigma3 Top-level Server (Web UI + MQTT Control + Telemetry)

This folder contains the **top-level server-side control software** for the Sigma3 stadium seat system.

It provides:
- A **Web UI** (Flask) for operators to trigger events (mode, goal, vote, animation, LED patterns).
- An **MQTT client** that publishes control commands to the Section Controller (Raspberry Pi) over Wi‑Fi.
- An **MQTT telemetry subscriber** that collects status updates from section controllers and shows them in the UI.

---

## 1) High-level architecture

```text
Operator (browser)
    ↓ HTTP
Flask Web UI (this repo)
    ↓ MQTT publish/subscribe
MQTT Broker (Mosquitto, etc.)
    ↓ Wi‑Fi
Section Controller (Raspberry Pi)
    ↓ (CAN bus) / (Audio lines)
Seat Nodes (MCUs)
```

**Important distinction**
- **Animation** in this project = *media playback on the Raspberry Pi* (pre-stored files).  
  The server only sends an `animation_id` and optional duration; Pi plays it locally.
- **LED control** = *lighting pattern control for seat LED bars* (e.g., Mexican wave).  
  The server sends a *pattern command*; Pi/seat firmware execute timing/positions.

---

## 2) Repository layout (what each folder is)

```text
sigma3-server/
├─ server/                  # Python package (Flask app + MQTT + logic)
│  ├─ __init__.py
│  ├─ app.py                 # Flask app factory + routes registration
│  ├─ config.py              # Configuration & environment variables
│  ├─ mqtt_client.py         # MQTT publish/subscribe wrapper (paho-mqtt)
│  ├─ messages.py            # Message schemas + builders (control + telemetry)
│  ├─ state.py               # In-memory telemetry store + helpers
│  ├─ routes.py              # Web UI routes (forms -> MQTT publish)
│  └─ utils.py               # Small helpers (time, validation, etc.)
├─ templates/                # Jinja2 HTML templates
│  └─ index.html
├─ static/                   # CSS/JS for the UI
│  ├─ styles.css
│  └─ app.js
├─ scripts/                  # Convenience scripts to run broker/app
│  ├─ run_dev.ps1
│  ├─ run_dev.sh
│  └─ start_mosquitto_docker.sh
├─ docs/                     # Extra documentation (per-file deep explanations)
│  ├─ FILES.md
│  ├─ MQTT_TOPICS.md
│  └─ MESSAGE_FORMATS.md
├─ tests/                    # Basic smoke tests (optional)
│  └─ test_message_builders.py
├─ .env.example              # Example env vars (copy to .env)
├─ requirements.txt
└─ LICENSE
```

If you are pushing to GitHub, keep this folder as `software/server/` (or similar) so the whole group can run it.

---

## 3) Quick start (works without any Raspberry Pi hardware)

### 3.1 Install Python deps
Use Python 3.10+ recommended.

```bash
python -m venv .venv
source .venv/bin/activate        # macOS/Linux
# .venv\Scripts\activate       # Windows PowerShell
pip install -r requirements.txt
```

### 3.2 Start an MQTT broker (choose one)

**Option A: Docker (recommended)**
```bash
./scripts/start_mosquitto_docker.sh
```

**Option B: Install Mosquitto locally**
- Windows: install Mosquitto and run it
- Ubuntu: `sudo apt install mosquitto mosquitto-clients`

### 3.3 Configure environment variables
Copy the example file and edit if needed:

```bash
cp .env.example .env
```

Default settings use:
- broker: `localhost`
- port: `1883`
- control topic: `stadium/section/{SECTION_ID}/control`
- telemetry topic: `stadium/section/+/telemetry`

### 3.4 Run the server
```bash
python -m server.app
```

Open:
- http://127.0.0.1:5000

You can click buttons; it will publish MQTT messages.

---

## 4) Connect to the Raspberry Pi (Section Controller)

Once the Pi is connected to the same network **and** is running code that:
- subscribes to the **control** topic
- publishes telemetry to the **telemetry** topic

…then the Web UI will:
- successfully send commands to the Pi
- show real telemetry in the “Section Status” table

The server does **not** need the Pi's IP address.  
Both sides just connect to the same MQTT broker.

---

## 5) How to modify (the most common changes)

### 5.1 Change topics
Edit `.env`:
- `MQTT_CONTROL_TOPIC_FMT`
- `MQTT_TELEMETRY_TOPIC`

See `docs/MQTT_TOPICS.md`.

### 5.2 Add a new command button to the UI
1. Add a new form in `templates/index.html`
2. Add a new route in `server/routes.py`
3. Build the message in `server/messages.py`

### 5.3 Change the payload format
All outgoing messages are built in `server/messages.py`.  
Update schemas there so the whole codebase stays consistent.

---

## 6) Troubleshooting

- **Nothing happens when I click buttons**
  - Ensure broker is running (`localhost:1883`)
  - Check `.env` broker address
  - Verify `server` console logs (“Published …”)

- **Section status table shows template text like `{{ s.section_id }}`**
  - That means the HTML is being served as a static file instead of rendered by Flask.
  - Make sure you run `python -m server.app` and access `http://127.0.0.1:5000`
  - Do **not** open `templates/index.html` directly in the browser.

- **Telemetry never appears**
  - Pi must publish telemetry JSON to `stadium/section/<id>/telemetry`
  - Telemetry payload must be valid JSON; see `docs/MESSAGE_FORMATS.md`

---

## 7) License
This repo is provided for your Sigma3 coursework project; update the license as required by your team.
