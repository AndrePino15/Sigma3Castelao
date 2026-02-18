# Run demo for Screen GUI (Qt + MQTT)
# Usage:
#   powershell -ExecutionPolicy Bypass -File .\run_demo.ps1

$ErrorActionPreference = "Stop"

Write-Host "=== Screen GUI Demo Runner ===" -ForegroundColor Cyan

# 0) Check commands
Write-Host "[0/4] Checking tools..." -ForegroundColor Yellow
docker --version | Out-Null
py --version | Out-Null

Write-Host ""
Write-Host "[1/4] Input API settings..." -ForegroundColor Yellow

$defaultKey = $env:API_FOOTBALL_KEY
$defaultFixture = $env:API_FIXTURE_ID

if ($defaultKey) {
    $keyIn = Read-Host "API_FOOTBALL_KEY (Enter to keep existing)"
} else {
    $keyIn = Read-Host "API_FOOTBALL_KEY"
}
if ([string]::IsNullOrWhiteSpace($keyIn)) {
    $keyIn = $defaultKey
}
if ([string]::IsNullOrWhiteSpace($keyIn)) {
    throw "API_FOOTBALL_KEY is required."
}
$env:API_FOOTBALL_KEY = $keyIn.Trim()

while ($true) {
    if ($defaultFixture) {
        $fixtureIn = Read-Host "API_FIXTURE_ID (Enter to keep existing: $defaultFixture)"
    } else {
        $fixtureIn = Read-Host "API_FIXTURE_ID (numeric)"
    }
    if ([string]::IsNullOrWhiteSpace($fixtureIn)) {
        $fixtureIn = $defaultFixture
    }
    if ($fixtureIn -and $fixtureIn -match '^\d+$') {
        $env:API_FIXTURE_ID = $fixtureIn
        break
    }
    Write-Host "Invalid fixture id. Please input a numeric value." -ForegroundColor Red
}
Write-Host "Using fixture id: $env:API_FIXTURE_ID" -ForegroundColor Green

# 1) Start MQTT broker (Mosquitto) in Docker
Write-Host ""
Write-Host "[2/4] Starting MQTT broker (Mosquitto)..." -ForegroundColor Yellow

$running = docker ps --filter "name=mqtt-broker" --format "{{.ID}}"
if (-not $running) {
    Write-Host "No running mqtt-broker found. Starting default mapping 1883:1883..." -ForegroundColor DarkYellow
    $existing = docker ps -a --filter "name=mqtt-broker" --format "{{.ID}}"
    if ($existing) {
        docker rm -f mqtt-broker | Out-Null
    }
    Start-Process -FilePath "cmd.exe" -ArgumentList "/c", "docker run -it --rm --name mqtt-broker -p 1883:1883 eclipse-mosquitto"
    Start-Sleep -Seconds 2
}

# Auto-detect host port mapped to container 1883/tcp.
$portLine = docker port mqtt-broker 1883/tcp 2>$null
$detectedPort = "1883"
if ($portLine -and ($portLine -match ":(\d+)$")) {
    $detectedPort = $Matches[1]
}
$env:MQTT_HOST = "127.0.0.1"
$env:MQTT_PORT = $detectedPort
Write-Host "Using MQTT: $env:MQTT_HOST`:$env:MQTT_PORT (auto-detected)" -ForegroundColor Green

# 2) Start fake server
Write-Host ""
Write-Host "[3/4] Starting fake_server.py ..." -ForegroundColor Yellow
Start-Process -FilePath "cmd.exe" -ArgumentList "/c", "py fake_server.py" -WorkingDirectory (Get-Location)

Start-Sleep -Seconds 1
Write-Host "Fake server started. In its window, type s to SAFETY, n to clear, q to quit." -ForegroundColor Green

# 3) Start Qt GUI
Write-Host ""
Write-Host "[4/4] Starting qt_gui.py ..." -ForegroundColor Yellow
Start-Process -FilePath "cmd.exe" -ArgumentList "/c", "py qt_gui.py" -WorkingDirectory (Get-Location)

Write-Host ""
Write-Host "Done. GUI should show CONNECTED and live data." -ForegroundColor Cyan
