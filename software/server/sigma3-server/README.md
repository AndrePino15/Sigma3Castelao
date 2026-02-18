# Sigma3 Stadium Seat System — Top-Level Server

This repository contains the **Top-Level Server** of the Sigma3 Smart Stadium Seat System.

The server is the central control unit of the stadium network.  
It provides a web interface for the operator, communicates with Raspberry Pi section controllers via MQTT, receives telemetry data, and simulates LED behaviour in a virtual stadium preview.

---

## System Architecture

The real system architecture is:

Web UI (Operator)
        ↓
Top-Level Server (this project)
        ↓ Wi-Fi / MQTT
Section Controller (Raspberry Pi 3B+)
        ↓ CAN Bus
Seat Node MCU
        ↓ GPIO
Seat LEDs / Buttons / Sensors

The server does **not directly control hardware**.  
Instead, it sends commands to the Raspberry Pi, which converts them into CAN messages for the seat nodes.

---

## Main Features

### 1. Operator Control Interface
The web panel allows an operator to trigger:

- Match events (goal, animation)
- Safety mode
- Audience voting
- LED patterns (Mexican wave, sparkle)

---

### 2. MQTT Control Publisher
The server publishes control commands over MQTT to the section controllers.

Example:
Server → Raspberry Pi → CAN → Seat Nodes

---

### 3. Telemetry Receiver
The Raspberry Pi sends back:

- Seat occupancy
- Votes
- Heartbeat
- Alerts

The server subscribes to these topics and displays them in the web UI.

---

### 4. Stadium Preview (Digital Twin)
The server includes a 2D stadium simulator.

It visually previews LED behaviour:
- Mexican wave
- Sparkle
- Section highlighting

This allows demonstration even with only **two prototype seats**.

---

## Project Structure

```
sigma3-server/
│
├── server/
│   ├── app.py
│   ├── routes.py
│   ├── messages.py
│   ├── state.py
│   └── __init__.py
│
├── templates/
│   └── index.html
│
├── static/
│   ├── app.js
│   └── styles.css
│
├── scripts/
│   └── start_mosquitto_docker.sh
│
├── requirements.txt
└── README.md
```

---

## File Explanation

### server/app.py
Main entry point of the server.

Responsibilities:
- Creates Flask application
- Connects to MQTT broker
- Subscribes to telemetry topics
- Starts the web server

Run using:
```
python3 -m server.app
```

---

### server/routes.py
Handles all button actions from the UI.

Examples:
- set_mode
- send_goal
- send_vote
- led_mexican_wave
- led_sparkle

It builds a command and publishes it via MQTT.

---

### server/messages.py
Defines the communication protocol.

Creates JSON commands sent to the Raspberry Pi.

Example:
```
{
  "type": "led_wave",
  "direction": "left_to_right",
  "speed": 12,
  "color": {"r":0,"g":120,"b":255}
}
```

---

### server/state.py
Stores temporary runtime information:

- Last LED command
- Section status
- Preview data

Used by the web preview system.

---

### templates/index.html
The operator control panel.

Contains:
- Control buttons
- Match events
- Voting interface
- LED control
- Stadium preview canvas

---

### static/app.js
Stadium preview engine.

Responsible for:
- Drawing elliptical stadium
- Dividing into sections
- Simulating LED animations

---

### static/styles.css
UI appearance and layout.

---

### scripts/start_mosquitto_docker.sh
Starts a Mosquitto MQTT broker using Docker.

---

## How to Run

### 1. Install dependencies

```
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

---

### 2. Start MQTT Broker

Option A (recommended):
```
./scripts/start_mosquitto_docker.sh
```

Option B:
```
mosquitto -v
```

---

### 3. Run Server

```
python3 -m server.app
```

Open browser:
```
http://127.0.0.1:5000
```

---

## Data Flow

When "Mexican Wave" is pressed:

Button press
→ Flask route
→ MQTT command
→ Raspberry Pi
→ CAN Bus
→ Seat Node LEDs

Simultaneously:

Server stores LED command
→ Browser requests preview
→ Virtual stadium lights up

This is a **Digital Twin simulation**.

---

## Common Problems

### TemplateNotFound
Cause:
index.html not inside templates folder.

Fix:
```
sigma3-server/templates/index.html
```

---

### MQTT Connection Refused
Broker not running.

Run:
```
mosquitto -v
```

---

### LED Preview Not Updating
Normal if Raspberry Pi is not connected.

The preview is a simulator.

---

## Why the Preview Exists

The coursework prototype has only **2 seats**.

The real design:
- 40,000 seats
- 40 sections
- 1000 seats per section

The preview demonstrates scalability and validates LED logic.

---

## Conclusion

This server is the software control layer of the Sigma3 stadium system.

It:
- Sends commands
- Receives telemetry
- Controls sections
- Simulates stadium behaviour

The Raspberry Pi and CAN network act as the hardware execution layer.