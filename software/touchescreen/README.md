# Screen GUI (PySide6 + MQTT + API-Football)

This project is a touchscreen-style Qt GUI built with PySide6.

It contains:
- Home page with animated menu and live match info panel
- Replay / Order / Info / Admin / Safety pages
- MQTT bridge for seat commands/telemetry
- API-Football integration with in-app cache strategy

## Requirements

- Python 3.10+
- See `requirements.txt` for exact package versions:
  - `paho-mqtt==2.1.0`
  - `PySide6==6.10.2`
  - `PySide6_Addons==6.10.2`
  - `PySide6_Essentials==6.10.2`
  - `shiboken6==6.10.2`
  - `requests==2.32.3`

Install dependencies:

```powershell
py -m pip install -r requirements.txt
```

## Startup Order (Important)

### Quick Start (recommended)

1. Start Docker Desktop.
2. In PowerShell, start MQTT broker container:

```powershell
docker run -it --rm --name mqtt-broker -p 1883:1883 eclipse-mosquitto
```

3. In project folder PowerShell, run:

```powershell
powershell -ExecutionPolicy Bypass -File .\run_demo.ps1
```

`run_demo.ps1` will prompt for:
- `API_FOOTBALL_KEY`
- `API_FIXTURE_ID`

Then it auto-detects MQTT mapped host port from Docker container `mqtt-broker`, and starts fake server + Qt app.

### Manual Start

1. Start Docker Desktop.
2. Start MQTT broker:

```powershell
docker run -it --rm --name mqtt-broker -p 1883:1883 eclipse-mosquitto
```

3. Configure API env vars:

```powershell
$env:API_FOOTBALL_KEY="your_api_football_key"
$env:API_FIXTURE_ID="<your_live_fixture_id>"
```

4. In project folder, start fake server:

```powershell
py fake_server.py
```

5. In another project folder terminal, start Qt app:

```powershell
py qt_gui.py
```

## Configure API Key and Fixture ID

The app reads:

- `API_FOOTBALL_KEY` (required)
- `API_FIXTURE_ID` (required)
- `MQTT_HOST` (optional, default `127.0.0.1`)
- `MQTT_PORT` (optional, default `1883`)

If missing, app shows:

- `Missing API_FOOTBALL_KEY environment variable`
- `Missing API_FIXTURE_ID environment variable`

## How To Get `fixture_id` (live)

Use API-Football live endpoint and pick one `fixture.id`.

```powershell
$env:API_FOOTBALL_KEY="your_api_football_key"
$h = @{ "x-apisports-key" = $env:API_FOOTBALL_KEY }
$r = Invoke-RestMethod -Uri "https://v3.football.api-sports.io/fixtures?live=all" -Headers $h
$r.response | Select-Object @{n="fixture_id";e={$_.fixture.id}}, @{n="home";e={$_.teams.home.name}}, @{n="away";e={$_.teams.away.name}}, @{n="score";e={"$($_.goals.home)-$($_.goals.away)"}}, @{n="status";e={$_.fixture.status.short}}
```

## API-Football Behavior

Current in-app middle-layer strategy:

- Upstream API pull every 30s (`API_UPSTREAM_MS`)
- UI cache publish every 3s (`API_CACHE_READ_MS`)
- Goal detected -> temporary boost pull every 8s for 2 minutes

This reduces third-party request usage while keeping UI responsive.

## Docker Usage

### Option A: Run directly with official Python image

```powershell
docker run --rm -it `
  -v "${PWD}:/app" `
  -w /app `
  -e API_FOOTBALL_KEY="your_api_football_key" `
  -e API_FIXTURE_ID="<your_live_fixture_id>" `
  -e MQTT_HOST="127.0.0.1" `
  -e MQTT_PORT="1883" `
  python:3.11 `
  sh -c "pip install -r requirements.txt && python qt_gui.py"
```

### Option B: Build image first

```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY . /app
RUN pip install --no-cache-dir -r requirements.txt
CMD ["python", "qt_gui.py"]
```

Build and run:

```powershell
docker build -t screen-gui-qt .
docker run --rm -it `
  -e API_FOOTBALL_KEY="your_api_football_key" `
  -e API_FIXTURE_ID="<your_live_fixture_id>" `
  -e MQTT_HOST="127.0.0.1" `
  -e MQTT_PORT="1883" `
  screen-gui-qt
```

## Custom MQTT Port (for multi-user conflict avoidance)

If `1883` is occupied, pick another host port, for example `1885`.

1. Start broker on custom host port:

```powershell
docker run -it --rm --name mqtt-broker -p 1885:1883 eclipse-mosquitto
```

2. Set app/fake-server to the same port:

```powershell
$env:MQTT_HOST="127.0.0.1"
$env:MQTT_PORT="1885"
```

3. Start `fake_server.py` and `qt_gui.py`, or run `run_demo.ps1` (it will auto-detect the mapped port from `mqtt-broker`).

## MQTT Topics

Configured in `qt_gui.py`:

- `stadium/seat/{SEAT_ID}/telemetry`
- `stadium/seat/{SEAT_ID}/cmd`
- `stadium/seat/{SEAT_ID}/ack`
- `stadium/broadcast/safety`

## Notes

- If API returns no data for some stats, UI shows `-`.
- For production, keep API key in env vars or a secret manager.
