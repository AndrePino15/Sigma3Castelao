"""Flask routes (Web UI -> MQTT publish).

How this file is organised:
- One route per button/action
- Each route:
  1) reads form fields
  2) builds a message dict using server/messages.py
  3) publishes via MQTT

This keeps UI and message schemas clean and testable.
"""

from __future__ import annotations

from flask import Blueprint, current_app, redirect, render_template, request, url_for, flash

from . import messages, state


bp = Blueprint("ui", __name__)


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
    section_id = request.form.get("section_id", cfg.default_section_id).strip() or cfg.default_section_id
    return section_id


@bp.post("/set_mode")
def set_mode():
    cfg = current_app.config["SIGMA3_CFG"]
    mqttc = current_app.config["SIGMA3_MQTT"]
    section_id = _get_section_id()
    mode = request.form.get("mode", "normal")
    reason = request.form.get("reason", "")

    try:
        msg = messages.build_mode_command(mode=mode, reason=reason)
        topic = cfg.mqtt_control_topic_fmt.format(section_id=section_id)
        mqttc.publish(topic, msg)
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
        topic = cfg.mqtt_control_topic_fmt.format(section_id=section_id)
        mqttc.publish(topic, msg)
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
        topic = cfg.mqtt_control_topic_fmt.format(section_id=section_id)
        mqttc.publish(topic, msg)
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
        topic = cfg.mqtt_control_topic_fmt.format(section_id=section_id)
        mqttc.publish(topic, msg)
        flash(f"Animation triggered: {animation_id} (section {section_id}).", "ok")
    except Exception as e:
        flash(f"Failed to play animation: {e}", "err")
    return redirect(url_for("ui.index"))


@bp.post("/led_mexican_wave")
def led_mexican_wave():
    cfg = current_app.config["SIGMA3_CFG"]
    mqttc = current_app.config["SIGMA3_MQTT"]
    section_id = _get_section_id()

    # Defaults are chosen to show an obvious wave
    direction = request.form.get("direction", "left_to_right")
    speed = int(request.form.get("speed_seats_per_s", "12") or 12)
    width = int(request.form.get("width_seats", "3") or 3)
    hold = int(request.form.get("hold_ms", "120") or 120)

    # Simple RGB inputs
    r = int(request.form.get("r", "0") or 0)
    g = int(request.form.get("g", "120") or 120)
    b = int(request.form.get("b", "255") or 255)

    try:
        msg = messages.build_led_command_mexican_wave(
            direction=direction,
            speed_seats_per_s=speed,
            width_seats=width,
            hold_ms=hold,
            color={"r": r, "g": g, "b": b},
        )
        topic = cfg.mqtt_control_topic_fmt.format(section_id=section_id)
        mqttc.publish(topic, msg)
        flash(f"LED Mexican wave sent (section {section_id}).", "ok")
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
        topic = cfg.mqtt_control_topic_fmt.format(section_id=section_id)
        mqttc.publish(topic, msg)
        flash(f"LED sparkle sent (section {section_id}).", "ok")
    except Exception as e:
        flash(f"Failed to send LED sparkle: {e}", "err")
    return redirect(url_for("ui.index"))
