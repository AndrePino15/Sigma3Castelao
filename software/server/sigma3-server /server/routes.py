from __future__ import annotations
import json
import queue
from flask import Blueprint, current_app, redirect, render_template, request, url_for, flash, jsonify, Response
from . import messages, state

bp = Blueprint("ui", __name__)

# -----------------------------------------------------------------------------
# Control Stream (SSE)
# - Broadcasts the latest control/preview command to any connected Web UI.
# - This makes the Stadium Preview responsive immediately after clicking buttons,
#   without requiring telemetry from Raspberry Pi.
# -----------------------------------------------------------------------------

_control_clients: list[queue.Queue] = []

def _broadcast_control_event(payload: dict) -> None:
    dead: list[queue.Queue] = []
    for q in _control_clients:
        try:
            q.put_nowait(payload)
        except Exception:
            dead.append(q)
    for q in dead:
        try:
            _control_clients.remove(q)
        except ValueError:
            pass

@bp.get("/control_stream")
def control_stream():
    """Server-Sent Events stream for control/preview events."""
    def gen():
        q: queue.Queue = queue.Queue()
        _control_clients.append(q)
        # Send the latest preview command immediately on connect (if any)
        latest = state.get_preview_led_command()
        if latest:
            yield f"data: {json.dumps({'type': 'preview', 'command': latest})}\n\n"
        try:
            while True:
                msg = q.get()
                yield f"data: {json.dumps(msg)}\n\n"
        finally:
            try:
                _control_clients.remove(q)
            except ValueError:
                pass

    return Response(gen(), mimetype="text/event-stream")

@bp.get("/")
def index():
    cfg = current_app.config["SIGMA3_CFG"]
    sections = state.get_all_sections()
    return render_template(
        "index.html",
        topic_control=cfg.mqtt_control_topic_fmt.format(section_id=cfg.default_section_id),
        topic_telemetry=cfg.mqtt_telemetry_topic,
        default_section=cfg.default_section_id,
        sections=sections,
    )

def _get_section_id() -> str:
    cfg = current_app.config["SIGMA3_CFG"]
    return (request.form.get("section_id", cfg.default_section_id).strip() or cfg.default_section_id)

# Preview API
@bp.get("/api/preview/command")
def api_preview_command():
    return jsonify({"ok": True, "command": state.get_preview_led_command()})

@bp.post("/set_mode")
def set_mode():
    cfg = current_app.config["SIGMA3_CFG"]
    mqttc = current_app.config["SIGMA3_MQTT"]
    section_id = _get_section_id()
    mode = request.form.get("mode", "normal")
    reason = request.form.get("reason", "")
    try:
        msg = messages.build_mode_command(mode=mode, reason=reason)
        mqttc.publish(cfg.mqtt_control_topic_fmt.format(section_id=section_id), msg)
        flash(f"Mode set to '{mode}' for section {section_id}.", "ok")
    except Exception as e:
        flash(f"Failed to set mode: {e}", "err")
    return redirect(url_for("ui.index"))

@bp.post("/send_goal")
def send_goal():
    cfg = current_app.config["SIGMA3_CFG"]
    mqttc = current_app.config["SIGMA3_MQTT"]
    section_id = _get_section_id()
    team = request.form.get("team", "home")
    try:
        msg = messages.build_goal_event(team=team)
        mqttc.publish(cfg.mqtt_control_topic_fmt.format(section_id=section_id), msg)
        flash(f"Goal event sent: {team} (section {section_id}).", "ok")
    except Exception as e:
        flash(f"Failed to send goal event: {e}", "err")
    return redirect(url_for("ui.index"))

@bp.post("/send_vote")
def send_vote():
    cfg = current_app.config["SIGMA3_CFG"]
    mqttc = current_app.config["SIGMA3_MQTT"]
    section_id = _get_section_id()
    vote_id = request.form.get("vote_id", "v1").strip() or "v1"
    duration_s = int(request.form.get("duration_s", "20") or 20)
    try:
        msg = messages.build_vote_command(vote_id=vote_id, duration_s=duration_s)
        mqttc.publish(cfg.mqtt_control_topic_fmt.format(section_id=section_id), msg)
        flash(f"Vote started: {vote_id} ({duration_s}s) for section {section_id}.", "ok")
    except Exception as e:
        flash(f"Failed to start vote: {e}", "err")
    return redirect(url_for("ui.index"))

@bp.post("/play_animation")
def play_animation():
    cfg = current_app.config["SIGMA3_CFG"]
    mqttc = current_app.config["SIGMA3_MQTT"]
    section_id = _get_section_id()
    animation_id = request.form.get("animation_id", "").strip()
    duration_s = float(request.form.get("duration_s", "0") or 0)
    try:
        msg = messages.build_animation_command(animation_id=animation_id, duration_s=duration_s)
        mqttc.publish(cfg.mqtt_control_topic_fmt.format(section_id=section_id), msg)
        flash(f"Animation triggered: {animation_id} (section {section_id}).", "ok")
    except Exception as e:
        flash(f"Failed to play animation: {e}", "err")
    return redirect(url_for("ui.index"))

@bp.post("/led_mexican_wave")
def led_mexican_wave():
    cfg = current_app.config["SIGMA3_CFG"]
    mqttc = current_app.config["SIGMA3_MQTT"]
    section_id = _get_section_id()

    direction = request.form.get("direction", "left_to_right")
    speed = int(request.form.get("speed_seats_per_s", "12") or 12)
    width = int(request.form.get("width_seats", "3") or 3)
    hold = int(request.form.get("hold_ms", "120") or 120)
    r = int(request.form.get("r", "0") or 0)
    g = int(request.form.get("g", "120") or 120)
    b = int(request.form.get("b", "255") or 255)

    try:
        msg = messages.build_led_command_mexican_wave(direction=direction, speed_seats_per_s=speed, width_seats=width, hold_ms=hold, color={"r": r, "g": g, "b": b})
        mqttc.publish(cfg.mqtt_control_topic_fmt.format(section_id=section_id), msg)

        preview_cmd = dict(msg)
        preview_cmd["section_id"] = section_id
        state.set_preview_led_command(preview_cmd)

        # Push to Web UI preview immediately
        _broadcast_control_event({"type": "preview", "command": preview_cmd})

        flash(f"LED Mexican wave sent (section {section_id}). Preview updated.", "ok")
    except Exception as e:
        flash(f"Failed to send LED wave: {e}", "err")
    return redirect(url_for("ui.index"))

@bp.post("/led_sparkle")
def led_sparkle():
    cfg = current_app.config["SIGMA3_CFG"]
    mqttc = current_app.config["SIGMA3_MQTT"]
    section_id = _get_section_id()
    duration_ms = int(request.form.get("duration_ms", "8000") or 8000)
    density = float(request.form.get("density", "0.08") or 0.08)
    try:
        msg = messages.build_led_command_sparkle(duration_ms=duration_ms, density=density)
        mqttc.publish(cfg.mqtt_control_topic_fmt.format(section_id=section_id), msg)

        preview_cmd = dict(msg)
        preview_cmd["section_id"] = section_id
        state.set_preview_led_command(preview_cmd)

        # Push to Web UI preview immediately
        _broadcast_control_event({"type": "preview", "command": preview_cmd})

        flash(f"LED sparkle sent (section {section_id}). Preview updated.", "ok")
    except Exception as e:
        flash(f"Failed to send LED sparkle: {e}", "err")
    return redirect(url_for("ui.index"))

@bp.post("/led_set_seat")
def led_set_seat():
    """Set a single seat LED (seat-level control) and update preview immediately."""
    cfg = current_app.config["SIGMA3_CFG"]
    mqttc = current_app.config["SIGMA3_MQTT"]
    section_id = _get_section_id()

    row = int(request.form.get("seat_row", "1") or 1)
    col = int(request.form.get("seat_col", "1") or 1)
    duration_ms = int(request.form.get("seat_duration_ms", "800") or 800)

    r = int(request.form.get("seat_r", "255") or 255)
    g = int(request.form.get("seat_g", "0") or 0)
    b = int(request.form.get("seat_b", "0") or 0)

    try:
        msg = messages.build_led_command_set_seat(
            section_id=section_id,
            row=row,
            col=col,
            color={"r": r, "g": g, "b": b},
            duration_ms=duration_ms,
        )
        # Publish to Pi (even if firmware doesn't implement yet, it can still receive/log it)
        mqttc.publish(cfg.mqtt_control_topic_fmt.format(section_id=section_id), msg)

        # Preview
        preview_cmd = dict(msg)
        preview_cmd["section_id"] = section_id
        state.set_preview_led_command(preview_cmd)
        _broadcast_control_event({"type": "preview", "command": preview_cmd})

        flash(f"Seat LED set: section {section_id}, row {row}, col {col}. Preview updated.", "ok")
    except Exception as e:
        flash(f"Failed to set seat LED: {e}", "err")

    return redirect(url_for("ui.index"))
