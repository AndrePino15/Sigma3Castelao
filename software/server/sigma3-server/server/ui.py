"""
Flask Web UI routes.

Key design goals:
- Multi-section input: section_ids can be '1' or '1,2,3' (and supports 'ALL')
- Persist user-entered values: state.set_last_inputs() per form
- Publish to per-section topics using SafeGoals scheme
- Provide preview events to browser via polling endpoint
- Live Audio: start/stop RTP(Opus) over UDP from server (Mac mic) -> Pi
"""

from flask import Blueprint, current_app, render_template, request, redirect, url_for, flash, jsonify
from typing import Dict, Any, List

from . import state
from .utils import parse_sections
from . import messages
from .mqtt_topics import control_topic, led_topic, emergency_topic
from .led.cue_service import CueService
from .led.preview_adapter import cue_to_preview_event

bp = Blueprint("ui", __name__)


def _default_sections() -> str:
    return current_app.config["SIGMA3_CFG"].default_sections


def _all_preview_sections() -> List[str]:
    """
    Preview only draws 1-10 in your app.js.
    So if user enters ALL, preview should affect 1-10.
    (MQTT publish for ALL is handled by expanding to configured section list if you add it later.)
    """
    return ["1", "2", "3", "4", "5", "6", "7", "8", "9", "10"]


def _expand_sections_for_actions(section_ids_raw: str) -> List[str]:
    """
    Expand user input into list of section IDs.
    Supports:
      - "1" or "1,2"
      - "ALL" -> all preview sections (1-10)
    """
    raw = (section_ids_raw or "").strip()
    if raw.upper() == "ALL":
        return _all_preview_sections()
    return parse_sections(raw)


def _get_sections_from_form() -> str:
    # allow empty => fallback
    return (request.form.get("section_ids") or "").strip() or _default_sections()


def _persist(form_name: str, fields: Dict[str, Any]) -> None:
    state.set_last_inputs(form_name, fields)


@bp.get("/")
def index():
    cfg = current_app.config["SIGMA3_CFG"]
    topic_examples = {
        "control": "safegoals/section/<section_id>/control",
        "led": "safegoals/section/<section_id>/led",
        "status": "safegoals/section/<section_id>/status",
        "emergency": "safegoals/emergency",
        "clock": "safegoals/show/clock",
    }

    # Render with persisted values (if any), otherwise defaults.
    defaults = {
        "section_ids": cfg.default_sections,
        "mode": "normal",
        "reason": "",
        "team": "home",
        "vote_id": "v1",
        "duration_s": 20,
        "animation_id": "goal_home",
        "anim_duration_s": 3.0,
        "direction": "left_to_right",
        "speed_seats_per_s": 12,
        "width_seats": 3,
        "hold_ms": 120,
        "r": 0, "g": 120, "b": 255,
        "spark_duration_ms": 8000,
        "spark_density": 0.08,
        "pix_row": 1,
        "pix_col": 1,
        "pix_hold_ms": 500,
        "cue_animation_id": "traveling_wave",
        "cue_duration_ms": 8000,
        "cue_loop": "false",
        "cue_dx": 1.0,
        "cue_dy": 0.0,
        "cue_speed": 8.0,
        "cue_seed": 42,
        "cue_id": "",

        # Live audio defaults (server->Pi)
        "audio_ip": getattr(cfg, "audio_target_ip", "172.20.10.2"),
        "audio_port": getattr(cfg, "audio_target_port", 5004),
    }

    # Merge last inputs from various forms
    for form in ["mode", "goal", "vote", "animation", "led_wave", "led_sparkle", "led_pixel", "led_cue", "emergency", "audio"]:
        defaults.update(state.get_last_inputs(form))

    telemetry = state.get_all_telemetry()
    section_rows = []
    for sid, payload in sorted(telemetry.items()):
        section_rows.append({"section_id": sid, "payload": payload})

    # Audio status (optional to show in UI if template uses it)
    audio = current_app.config.get("SIGMA3_AUDIO")
    audio_status = None
    if audio is not None:
        try:
            audio_status = audio.status()
        except Exception:
            audio_status = None

    return render_template(
        "index.html",
        topic_examples=topic_examples,
        section_rows=section_rows,
        defaults=defaults,
        audio_status=audio_status,
    )


# -------- CONTROL --------
@bp.post("/set_mode")
def set_mode():
    mqttc = current_app.config["SIGMA3_MQTT"]
    section_ids_raw = _get_sections_from_form()
    mode = request.form.get("mode", "normal")
    reason = request.form.get("reason", "")

    _persist("mode", {"section_ids": section_ids_raw, "mode": mode, "reason": reason})

    msg = messages.build_mode(mode=mode, reason=reason)
    for sid in _expand_sections_for_actions(section_ids_raw):
        mqttc.publish(control_topic(sid), msg)

    flash(f"Mode sent to {section_ids_raw}", "ok")
    return redirect(url_for("ui.index"))


@bp.post("/send_goal")
def send_goal():
    mqttc = current_app.config["SIGMA3_MQTT"]
    section_ids_raw = _get_sections_from_form()
    team = request.form.get("team", "home")

    _persist("goal", {"section_ids": section_ids_raw, "team": team})

    msg = messages.build_goal(team=team)
    for sid in _expand_sections_for_actions(section_ids_raw):
        mqttc.publish(control_topic(sid), msg)

    flash(f"Goal sent to {section_ids_raw} (team={team})", "ok")
    return redirect(url_for("ui.index"))


@bp.post("/send_vote")
def send_vote():
    mqttc = current_app.config["SIGMA3_MQTT"]
    section_ids_raw = _get_sections_from_form()
    vote_id = request.form.get("vote_id", "v1")
    duration_s = int(request.form.get("duration_s", "20") or 20)

    _persist("vote", {"section_ids": section_ids_raw, "vote_id": vote_id, "duration_s": duration_s})

    msg = messages.build_vote(vote_id=vote_id, duration_s=duration_s)
    for sid in _expand_sections_for_actions(section_ids_raw):
        mqttc.publish(control_topic(sid), msg)

    flash(f"Vote started in {section_ids_raw}", "ok")
    return redirect(url_for("ui.index"))


@bp.post("/play_animation")
def play_animation():
    mqttc = current_app.config["SIGMA3_MQTT"]
    section_ids_raw = _get_sections_from_form()
    animation_id = request.form.get("animation_id", "goal_home")
    duration_s = float(request.form.get("anim_duration_s", "3.0") or 3.0)

    _persist("animation", {"section_ids": section_ids_raw, "animation_id": animation_id, "anim_duration_s": duration_s})

    msg = messages.build_animation(animation_id=animation_id, duration_s=duration_s)
    for sid in _expand_sections_for_actions(section_ids_raw):
        mqttc.publish(control_topic(sid), msg)

    flash(f"Animation '{animation_id}' sent to {section_ids_raw}", "ok")
    return redirect(url_for("ui.index"))


@bp.post("/send_emergency")
def send_emergency():
    mqttc = current_app.config["SIGMA3_MQTT"]
    reason = request.form.get("emergency_reason", "emergency")

    _persist("emergency", {"emergency_reason": reason})

    msg = messages.build_emergency(reason=reason)
    mqttc.publish(emergency_topic(), msg)

    flash("Emergency broadcast sent", "warn")
    return redirect(url_for("ui.index"))


# -------- LED --------
@bp.post("/led_mexican_wave")
def led_mexican_wave():
    mqttc = current_app.config["SIGMA3_MQTT"]
    section_ids_raw = _get_sections_from_form()
    direction = request.form.get("direction", "left_to_right")
    speed = int(request.form.get("speed_seats_per_s", "12") or 12)
    width = int(request.form.get("width_seats", "3") or 3)
    hold = int(request.form.get("hold_ms", "120") or 120)
    r = int(request.form.get("r", "0") or 0)
    g = int(request.form.get("g", "120") or 120)
    b = int(request.form.get("b", "255") or 255)

    _persist("led_wave", {
        "section_ids": section_ids_raw,
        "direction": direction,
        "speed_seats_per_s": speed,
        "width_seats": width,
        "hold_ms": hold,
        "r": r, "g": g, "b": b,
    })

    msg = messages.build_led_mexican_wave(
        direction=direction,
        speed_seats_per_s=speed,
        width_seats=width,
        hold_ms=hold,
        rgb={"r": r, "g": g, "b": b},
    )
    sections = _expand_sections_for_actions(section_ids_raw)
    for sid in sections:
        mqttc.publish(led_topic(sid), msg)

    # Push preview event (for browser simulator)
    state.set_preview_event({
        "kind": "led",
        "pattern": "mexican_wave",
        "sections": sections,
        "params": msg["payload"],
    })

    flash(f"LED Mexican wave sent to {section_ids_raw}", "ok")
    return redirect(url_for("ui.index"))


@bp.post("/led_sparkle")
def led_sparkle():
    mqttc = current_app.config["SIGMA3_MQTT"]
    section_ids_raw = _get_sections_from_form()
    duration_ms = int(request.form.get("spark_duration_ms", "8000") or 8000)
    density = float(request.form.get("spark_density", "0.08") or 0.08)
    r = int(request.form.get("r", "0") or 0)
    g = int(request.form.get("g", "120") or 120)
    b = int(request.form.get("b", "255") or 255)

    _persist("led_sparkle", {
        "section_ids": section_ids_raw,
        "spark_duration_ms": duration_ms,
        "spark_density": density,
        "r": r, "g": g, "b": b,
    })

    msg = messages.build_led_sparkle(duration_ms=duration_ms, density=density, rgb={"r": r, "g": g, "b": b})
    sections = _expand_sections_for_actions(section_ids_raw)
    for sid in sections:
        mqttc.publish(led_topic(sid), msg)

    state.set_preview_event({
        "kind": "led",
        "pattern": "sparkle",
        "sections": sections,
        "params": msg["payload"],
    })

    flash(f"LED Sparkle sent to {section_ids_raw}", "ok")
    return redirect(url_for("ui.index"))


@bp.post("/led_set_pixel")
def led_set_pixel():
    mqttc = current_app.config["SIGMA3_MQTT"]
    section_ids_raw = _get_sections_from_form()
    row = int(request.form.get("pix_row", "1") or 1)
    col = int(request.form.get("pix_col", "1") or 1)
    hold_ms = int(request.form.get("pix_hold_ms", "500") or 500)
    r = int(request.form.get("r", "0") or 0)
    g = int(request.form.get("g", "120") or 120)
    b = int(request.form.get("b", "255") or 255)

    _persist("led_pixel", {
        "section_ids": section_ids_raw,
        "pix_row": row,
        "pix_col": col,
        "pix_hold_ms": hold_ms,
        "r": r, "g": g, "b": b,
    })

    msg = messages.build_led_set_pixel(row=row, col=col, rgb={"r": r, "g": g, "b": b}, hold_ms=hold_ms)
    sections = _expand_sections_for_actions(section_ids_raw)
    for sid in sections:
        mqttc.publish(led_topic(sid), msg)

    state.set_preview_event({
        "kind": "led",
        "pattern": "set_pixel",
        "sections": sections,
        "params": msg["payload"],
    })

    flash(f"LED Pixel set sent to {section_ids_raw} (row={row}, col={col})", "ok")
    return redirect(url_for("ui.index"))


@bp.post("/led_cue_start")
def led_cue_start():
    cfg = current_app.config["SIGMA3_CFG"]
    section_ids_raw = _get_sections_from_form()
    sections = _expand_sections_for_actions(section_ids_raw)

    animation_id = request.form.get("cue_animation_id", "traveling_wave")
    duration_ms = int(request.form.get("cue_duration_ms", "8000") or 8000)
    loop = (request.form.get("cue_loop", "false").lower() == "true")
    dx = float(request.form.get("cue_dx", "1.0") or 1.0)
    dy = float(request.form.get("cue_dy", "0.0") or 0.0)
    speed = float(request.form.get("cue_speed", "8.0") or 8.0)
    seed = int(request.form.get("cue_seed", "42") or 42)
    params = {
        "dx": dx,
        "dy": dy,
        "speed_units_per_s": speed,
        "palette": [[0, 0, 0], [0, 120, 255]],
        "seed": seed,
    }

    _persist("led_cue", {
        "section_ids": section_ids_raw,
        "cue_animation_id": animation_id,
        "cue_duration_ms": duration_ms,
        "cue_loop": str(loop).lower(),
        "cue_dx": dx,
        "cue_dy": dy,
        "cue_speed": speed,
        "cue_seed": seed,
        "cue_id": "",
    })

    cue_service = current_app.config.get("SIGMA3_LED_CUE") or CueService(current_app.config["SIGMA3_MQTT"])
    last_cue_id = None
    for sid in sections:
        last_cue_id = cue_service.publish_cue_start(
            sid,
            animation_id,
            params,
            duration_ms=duration_ms,
            loop=loop,
            lead_ms=getattr(cfg, "cue_start_lead_ms", 500),
        )

    if last_cue_id:
        state.set_preview_event(cue_to_preview_event(sections, {
            "cue_id": last_cue_id,
            "animation_id": animation_id,
            "duration_ms": duration_ms,
            "loop": loop,
            "params": params,
        }))
    flash(f"LED cue '{animation_id}' sent to {section_ids_raw}", "ok")
    return redirect(url_for("ui.index"))


@bp.post("/led_cue_stop")
def led_cue_stop():
    section_ids_raw = _get_sections_from_form()
    sections = _expand_sections_for_actions(section_ids_raw)
    cue_id = (request.form.get("cue_id") or "").strip()
    if not cue_id:
        flash("cue_id is required", "err")
        return redirect(url_for("ui.index"))
    _persist("led_cue", {"section_ids": section_ids_raw, "cue_id": cue_id})
    cue_service = current_app.config.get("SIGMA3_LED_CUE") or CueService(current_app.config["SIGMA3_MQTT"])
    for sid in sections:
        cue_service.publish_cue_stop(sid, cue_id)
    flash(f"LED cue stop sent to {section_ids_raw}", "ok")
    return redirect(url_for("ui.index"))


# -------- PREVIEW API (browser polls) --------
@bp.get("/api/preview/poll")
def preview_poll():
    evt = state.pop_preview_event()
    return jsonify(evt or {"kind": "none"})


# -------- LIVE AUDIO (Server Mac mic -> Pi RTP/Opus over UDP) --------
@bp.post("/audio_start")
def audio_start():
    cfg = current_app.config["SIGMA3_CFG"]
    audio = current_app.config["SIGMA3_AUDIO"]

    target_ip = (request.form.get("audio_ip") or cfg.audio_target_ip).strip()
    target_port = int(request.form.get("audio_port") or cfg.audio_target_port)

    _persist("audio", {"audio_ip": target_ip, "audio_port": target_port})

    try:
        # start/retarget stream
        audio.start(target_ip=target_ip, target_port=target_port)
        st = audio.status()
        if st["running"]:
            flash(f"Live audio started -> {target_ip}:{target_port}", "ok")
        else:
            flash(f"Live audio failed: {st.get('last_error')}", "err")
    except Exception as e:
        flash(f"Failed to start audio RTP: {e}", "err")

    return redirect(url_for("ui.index"))


@bp.post("/audio_stop")
def audio_stop():
    audio = current_app.config["SIGMA3_AUDIO"]
    try:
        audio.stop()
        flash("Live audio stopped", "ok")
    except Exception as e:
        flash(f"Failed to stop audio RTP: {e}", "err")

    return redirect(url_for("ui.index"))
