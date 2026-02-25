#!/usr/bin/env bash
set -euo pipefail

# Load local config file first so user can run "./start_gui.sh" directly.
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONFIG_FILE="${CONFIG_FILE:-$SCRIPT_DIR/start_gui.env}"
if [[ -f "$CONFIG_FILE" ]]; then
  # shellcheck disable=SC1090
  source "$CONFIG_FILE"
fi

# Runtime defaults.
MQTT_HOST="${MQTT_HOST:-127.0.0.1}"
MQTT_PORT="${MQTT_PORT:-1883}"
FIXTURE_TOPIC="${FIXTURE_TOPIC:-stadium/config/fixture_id}"
APP_DIR="${APP_DIR:-$SCRIPT_DIR}"
VENV_DIR="${VENV_DIR:-$APP_DIR/.venv}"
WAIT_SEC="${WAIT_SEC:-30}"
HIDE_PANEL="${HIDE_PANEL:-0}"
PANEL_GUARD="${PANEL_GUARD:-0}"
PANEL_GUARD_SLEEP_SEC="${PANEL_GUARD_SLEEP_SEC:-1}"

# When launching from SSH, desktop-session env vars may be missing.
# Provide sane defaults so accessibility/OSK services can attach.
USER_ID="$(id -u)"
XDG_RUNTIME_DIR="${XDG_RUNTIME_DIR:-/run/user/$USER_ID}"
DBUS_SESSION_BUS_ADDRESS="${DBUS_SESSION_BUS_ADDRESS:-unix:path=$XDG_RUNTIME_DIR/bus}"
QT_ACCESSIBILITY="${QT_ACCESSIBILITY:-1}"
QT_LINUX_ACCESSIBILITY_ALWAYS_ON="${QT_LINUX_ACCESSIBILITY_ALWAYS_ON:-1}"
export XDG_RUNTIME_DIR DBUS_SESSION_BUS_ADDRESS QT_ACCESSIBILITY QT_LINUX_ACCESSIBILITY_ALWAYS_ON

if [[ -z "${API_FOOTBALL_KEY:-}" ]]; then
  echo "Missing API_FOOTBALL_KEY environment variable"
  exit 1
fi

PANEL_MODE=""
PANEL_GUARD_PID=""

hide_panel() {
  if command -v lxpanelctl >/dev/null 2>&1; then
    lxpanelctl exit >/dev/null 2>&1 || true
    PANEL_MODE="lxpanel"
    return
  fi
  if command -v wf-panel-pi >/dev/null 2>&1; then
    killall wf-panel-pi >/dev/null 2>&1 || true
    PANEL_MODE="wf-panel-pi"
    return
  fi
}

start_panel_guard() {
  if [[ "$PANEL_GUARD" != "1" ]]; then
    return
  fi
  case "$PANEL_MODE" in
    lxpanel)
      (
        while true; do
          pkill -x lxpanel >/dev/null 2>&1 || true
          sleep "$PANEL_GUARD_SLEEP_SEC"
        done
      ) &
      PANEL_GUARD_PID="$!"
      ;;
    wf-panel-pi)
      (
        while true; do
          pkill -x wf-panel-pi >/dev/null 2>&1 || true
          sleep "$PANEL_GUARD_SLEEP_SEC"
        done
      ) &
      PANEL_GUARD_PID="$!"
      ;;
  esac
}

stop_panel_guard() {
  if [[ -n "$PANEL_GUARD_PID" ]]; then
    kill "$PANEL_GUARD_PID" >/dev/null 2>&1 || true
    wait "$PANEL_GUARD_PID" 2>/dev/null || true
    PANEL_GUARD_PID=""
  fi
}

restore_panel() {
  stop_panel_guard
  case "$PANEL_MODE" in
    lxpanel)
      if command -v lxpanel >/dev/null 2>&1; then
        lxpanel --profile LXDE-pi >/dev/null 2>&1 &
      fi
      ;;
    wf-panel-pi)
      if command -v wf-panel-pi >/dev/null 2>&1; then
        wf-panel-pi >/dev/null 2>&1 &
      fi
      ;;
  esac
}

trap restore_panel EXIT

echo "Reading fixture_id from MQTT..."
echo "Broker: ${MQTT_HOST}:${MQTT_PORT}"
echo "Topic : ${FIXTURE_TOPIC}"

# -C 1: receive one message then exit
# -W N: timeout (seconds)
FIXTURE_ID="$(mosquitto_sub -h "$MQTT_HOST" -p "$MQTT_PORT" -t "$FIXTURE_TOPIC" -C 1 -W "$WAIT_SEC" || true)"

if [[ -z "$FIXTURE_ID" ]]; then
  echo "No fixture_id received within ${WAIT_SEC}s from topic ${FIXTURE_TOPIC}"
  exit 1
fi

if ! [[ "$FIXTURE_ID" =~ ^[0-9]+$ ]]; then
  echo "Invalid fixture_id received: '$FIXTURE_ID'"
  exit 1
fi

export API_FIXTURE_ID="$FIXTURE_ID"
export MQTT_HOST MQTT_PORT

echo "Using fixture_id: ${API_FIXTURE_ID}"

cd "$APP_DIR"
source "$VENV_DIR/bin/activate"
if [[ "$HIDE_PANEL" == "1" ]]; then
  hide_panel
  start_panel_guard
fi
python qt_gui.py
