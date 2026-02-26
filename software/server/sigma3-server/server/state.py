"""In-memory state for the demo server.

- last_inputs: remembers the last values you typed in forms
- telemetry: latest status message per section
- preview_event: last LED preview event pushed to the browser
"""
from dataclasses import dataclass, field
from typing import Dict, Any, Optional
import threading

_lock = threading.Lock()

last_inputs: Dict[str, Dict[str, Any]] = {}  # form_name -> fields dict
telemetry_by_section: Dict[str, Dict[str, Any]] = {}
preview_event: Optional[Dict[str, Any]] = None

def set_last_inputs(form_name: str, fields: Dict[str, Any]) -> None:
    with _lock:
        last_inputs[form_name] = dict(fields)

def get_last_inputs(form_name: str) -> Dict[str, Any]:
    with _lock:
        return dict(last_inputs.get(form_name, {}))

def update_telemetry(section_id: str, payload: Dict[str, Any]) -> None:
    with _lock:
        telemetry_by_section[section_id] = payload

def get_all_telemetry() -> Dict[str, Dict[str, Any]]:
    with _lock:
        return dict(telemetry_by_section)

def set_preview_event(evt: Dict[str, Any]) -> None:
    with _lock:
        global preview_event
        preview_event = dict(evt)

def pop_preview_event() -> Optional[Dict[str, Any]]:
    with _lock:
        global preview_event
        evt = preview_event
        preview_event = None
        return evt
