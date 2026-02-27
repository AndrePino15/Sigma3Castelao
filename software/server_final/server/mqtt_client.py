"""MQTT client wrapper (paho-mqtt).

- Connects to broker
- Subscribes to status wildcard topic
- Calls state.update_telemetry() when status messages arrive
"""
import json
import threading
from typing import Any, Optional
import time

import paho.mqtt.client as mqtt

from .runtime_config import RuntimeConfig
from . import state
from .mqtt_topics import (
    status_wildcard,
    screen_cmd_wildcard,
    emergency_topic,
    screen_safety_topic,
)

class MqttClient:
    def __init__(self, cfg: RuntimeConfig):
        self.cfg = cfg
        self._client = mqtt.Client()
        self._thread: Optional[threading.Thread] = None
        self._last_safety_forward_ts = 0.0

        self._client.on_connect = self._on_connect
        self._client.on_message = self._on_message

    def start(self) -> None:
        # Connect and start network loop in background.
        self._client.connect(self.cfg.mqtt_host, self.cfg.mqtt_port, keepalive=30)
        self._client.loop_start()

    def publish(self, topic: str, msg: Any, qos: int = 0, retain: bool = False) -> None:
        payload = json.dumps(msg)
        self._client.publish(topic, payload=payload, qos=qos, retain=retain)

    def publish_text(self, topic: str, payload: str, qos: int = 0, retain: bool = False) -> None:
        self._client.publish(topic, payload=str(payload), qos=qos, retain=retain)

    def _on_connect(self, client, userdata, flags, rc):
        # Subscribe to team status topics and screen uplink command topics.
        client.subscribe(status_wildcard())
        client.subscribe(screen_cmd_wildcard())
        client.subscribe(emergency_topic(), qos=1)

    def _forward_screen_safety(self, msg: str, *, level: str = "CRITICAL", min_interval_s: float = 2.0) -> None:
        """
        Forward a safety broadcast to screen topic with basic throttling.
        This prevents flooding when heartbeat/status messages repeat safety state.
        """
        now = time.time()
        if (now - self._last_safety_forward_ts) < float(min_interval_s):
            return
        self._last_safety_forward_ts = now
        self.publish(
            screen_safety_topic(),
            {
                "ts": int(now),
                "mode": "SAFETY",
                "level": str(level).upper(),
                "msg": str(msg).strip() or "Emergency",
            },
            qos=1,
        )

    def _on_message(self, client, userdata, msg):
        try:
            topic = msg.topic
            raw = msg.payload.decode("utf-8", errors="ignore").strip()
            data = json.loads(raw) if raw else {}

            if topic == emergency_topic():
                reason = "Emergency broadcast"
                if isinstance(data, dict):
                    if isinstance(data.get("payload"), dict):
                        reason = str(data["payload"].get("reason") or reason)
                    else:
                        reason = str(data.get("reason") or reason)
                self._forward_screen_safety(reason, level="CRITICAL", min_interval_s=1.0)
                return

            if topic.startswith("safegoals/section/") and topic.endswith("/status"):
                parts = topic.split("/")
                # parts: ["safegoals","section","<id>","status"]
                section_id = parts[2] if len(parts) >= 4 else "?"
                state.update_telemetry(section_id, data if isinstance(data, dict) else {"raw": data})
                # Generic compatibility: if section status explicitly reports emergency,
                # forward it to screen safety topic as well.
                if isinstance(data, dict):
                    t = str(data.get("type", "")).strip().lower()
                    emergency_flag = bool(data.get("emergency", False))
                    if t == "emergency" or emergency_flag:
                        reason = (
                            data.get("reason")
                            or data.get("msg")
                            or data.get("message")
                            or f"Emergency from section {section_id}"
                        )
                        self._forward_screen_safety(
                            str(reason),
                            level="CRITICAL",
                            min_interval_s=1.0,
                        )
                # Compatibility path:
                # section-controller currently uplinks vote result in status seat_event
                # (voted/vote flags), not stadium/seat/<id>/cmd VOTE.
                if isinstance(data, dict) and str(data.get("type", "")).lower() == "seat_event":
                    if bool(data.get("voted", False)) and data.get("vote") in (True, False):
                        defaults = state.get_vote_ingest_defaults()
                        section_raw = data.get("section", section_id)
                        section_str = str(section_raw).strip() or str(section_id)
                        seat_num = data.get("seat_id")
                        if seat_num is None:
                            seat_num = data.get("seat")
                        node_num = data.get("node_id")
                        if isinstance(seat_num, int):
                            seat_id = f"section{section_str},row1,col{seat_num + 1}"
                        elif isinstance(node_num, int):
                            seat_id = f"section{section_str},row1,col{node_num}"
                        else:
                            seat_id = f"section{section_str},row1,colunknown"

                        state.add_vote(
                            seat_id=seat_id,
                            vote_id=defaults["vote_id"],
                            player=defaults["player"],
                            choice="yes" if bool(data.get("vote")) else "no",
                            ts=int(time.time()),
                        )
                    # Also auto-forward safety to screen when SOS is raised.
                    if bool(data.get("sos", False)):
                        seat_for_msg = data.get("seat_id")
                        if seat_for_msg is None:
                            seat_for_msg = data.get("seat")
                        self._forward_screen_safety(
                            f"SOS from section {section_id}, seat {seat_for_msg}",
                            level="CRITICAL",
                            min_interval_s=1.0,
                        )
                # Section heartbeat in SAFETY mode should also trigger screen safety page.
                if isinstance(data, dict) and str(data.get("type", "")).lower() == "section_heartbeat":
                    if str(data.get("mode", "")).upper() == "SAFETY":
                        self._forward_screen_safety(
                            f"Section {section_id} entered SAFETY mode",
                            level="CRITICAL",
                            min_interval_s=5.0,
                        )
                return

            if topic.startswith("stadium/seat/") and topic.endswith("/cmd"):
                parts = topic.split("/")
                # parts: ["stadium","seat","<seat_id>","cmd"]
                seat_id = parts[2] if len(parts) >= 4 else "?"
                cmd = str(data.get("cmd", "")).upper() if isinstance(data, dict) else ""
                if cmd == "ORDER":
                    payload = data.get("payload", {}) if isinstance(data, dict) else {}
                    state.add_order({
                        "rx_ts": int(time.time()),
                        "seat_id": seat_id,
                        "cmd": cmd,
                        "item": payload.get("item", ""),
                        "qty": payload.get("qty", ""),
                        "note": payload.get("note", ""),
                        "raw": data,
                    })
                    return
                if cmd == "VOTE":
                    payload = data.get("payload", {}) if isinstance(data, dict) else {}
                    vote_id = str(
                        payload.get("vote_id")
                        or data.get("vote_id")
                        or "mvp_live"
                    ).strip()
                    player = str(
                        payload.get("player")
                        or payload.get("candidate")
                        or payload.get("name")
                        or ""
                    ).strip()
                    choice = str(
                        payload.get("choice")
                        or payload.get("vote")
                        or data.get("choice")
                        or ""
                    ).strip()
                    ts = int(time.time())
                    raw_ts = payload.get("ts") if isinstance(payload, dict) else None
                    if raw_ts is not None:
                        try:
                            ts = int(raw_ts)
                        except Exception:
                            ts = int(time.time())
                    state.add_vote(
                        seat_id=seat_id,
                        vote_id=vote_id,
                        player=player,
                        choice=choice,
                        ts=ts,
                    )
                return
        except Exception:
            # swallow errors in demo; you can log later
            return
