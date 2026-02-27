"""In-memory state for the demo server.

- last_inputs: remembers the last values you typed in forms
- telemetry: latest status message per section
- preview_event: last LED preview event pushed to the browser
- orders: recent ORDER uplinks received from screen seats
- votes: per-player YES/NO stats keyed by vote_id
"""
from typing import Dict, Any, Optional, List
import threading

_lock = threading.Lock()

last_inputs: Dict[str, Dict[str, Any]] = {}  # form_name -> fields dict
telemetry_by_section: Dict[str, Dict[str, Any]] = {}
preview_event: Optional[Dict[str, Any]] = None
recent_orders: List[Dict[str, Any]] = []
MAX_ORDERS = 30
vote_active_id: str = ""
vote_players_by_id: Dict[str, List[str]] = {}
vote_seat_choice_by_id: Dict[str, Dict[str, Dict[str, Any]]] = {}
vote_counts_by_id: Dict[str, Dict[str, Dict[str, int]]] = {}

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


def add_order(order: Dict[str, Any]) -> None:
    with _lock:
        recent_orders.insert(0, dict(order))
        del recent_orders[MAX_ORDERS:]


def get_recent_orders() -> List[Dict[str, Any]]:
    with _lock:
        return [dict(x) for x in recent_orders]


def _norm_vote_id(vote_id: str) -> str:
    v = str(vote_id or "").strip()
    return v if v else "mvp_live"


def _norm_player(player: str) -> str:
    return str(player or "").strip()


def _norm_choice(choice: str) -> str:
    c = str(choice or "").strip().lower()
    if c in ("yes", "y", "1", "true", "ok"):
        return "yes"
    if c in ("no", "n", "0", "false"):
        return "no"
    return ""


def _ensure_vote_store(vote_id: str) -> None:
    if vote_id not in vote_players_by_id:
        vote_players_by_id[vote_id] = []
    if vote_id not in vote_seat_choice_by_id:
        vote_seat_choice_by_id[vote_id] = {}
    if vote_id not in vote_counts_by_id:
        vote_counts_by_id[vote_id] = {}


def _ensure_player_counter(vote_id: str, player: str) -> Dict[str, int]:
    counters = vote_counts_by_id[vote_id]
    if player not in counters:
        counters[player] = {"yes": 0, "no": 0}
    return counters[player]


def open_vote(vote_id: str, players: List[str]) -> None:
    """Start/reset a vote session and optional player list."""
    cleaned_players: List[str] = []
    for p in players:
        pp = _norm_player(p)
        if pp and pp not in cleaned_players:
            cleaned_players.append(pp)

    vid = _norm_vote_id(vote_id)
    with _lock:
        global vote_active_id
        vote_active_id = vid
        vote_players_by_id[vid] = cleaned_players
        vote_seat_choice_by_id[vid] = {}
        vote_counts_by_id[vid] = {p: {"yes": 0, "no": 0} for p in cleaned_players}


def set_vote_players(vote_id: str, players: List[str]) -> None:
    vid = _norm_vote_id(vote_id)
    cleaned_players: List[str] = []
    for p in players:
        pp = _norm_player(p)
        if pp and pp not in cleaned_players:
            cleaned_players.append(pp)

    with _lock:
        global vote_active_id
        vote_active_id = vid
        _ensure_vote_store(vid)
        # Keep already known players and append new ones.
        existing = list(vote_players_by_id.get(vid, []))
        for p in cleaned_players:
            if p not in existing:
                existing.append(p)
        vote_players_by_id[vid] = existing
        for p in existing:
            _ensure_player_counter(vid, p)


def add_vote(seat_id: str, vote_id: str, player: str, choice: str, ts: int) -> bool:
    """Record seat vote. One seat keeps one latest vote per vote_id."""
    sid = str(seat_id or "").strip()
    vid = _norm_vote_id(vote_id)
    ply = _norm_player(player)
    ch = _norm_choice(choice)
    if not sid or not ply or not ch:
        return False

    with _lock:
        global vote_active_id
        vote_active_id = vid
        _ensure_vote_store(vid)

        # Ensure player appears in configured list.
        if ply not in vote_players_by_id[vid]:
            vote_players_by_id[vid].append(ply)
        _ensure_player_counter(vid, ply)

        seat_map = vote_seat_choice_by_id[vid]
        prev = seat_map.get(sid)
        if prev is not None:
            prev_player = _norm_player(prev.get("player", ""))
            prev_choice = _norm_choice(prev.get("choice", ""))
            if prev_player and prev_choice:
                prev_counter = _ensure_player_counter(vid, prev_player)
                prev_counter[prev_choice] = max(0, int(prev_counter.get(prev_choice, 0)) - 1)

        seat_map[sid] = {"player": ply, "choice": ch, "ts": int(ts)}
        curr_counter = _ensure_player_counter(vid, ply)
        curr_counter[ch] = int(curr_counter.get(ch, 0)) + 1
    return True


def get_vote_board(vote_id: str = "") -> Dict[str, Any]:
    vid = _norm_vote_id(vote_id or vote_active_id)
    with _lock:
        _ensure_vote_store(vid)
        players = list(vote_players_by_id.get(vid, []))
        counters = vote_counts_by_id.get(vid, {})
        seat_map = vote_seat_choice_by_id.get(vid, {})

        # Include players that only appeared in counts.
        for p in counters.keys():
            if p not in players:
                players.append(p)

        rows: List[Dict[str, Any]] = []
        total_yes = 0
        total_no = 0
        for p in players:
            c = counters.get(p, {"yes": 0, "no": 0})
            yes = int(c.get("yes", 0))
            no = int(c.get("no", 0))
            total_yes += yes
            total_no += no
            rows.append({
                "player": p,
                "yes": yes,
                "no": no,
                "total": yes + no,
            })

        rows.sort(key=lambda x: (-x["yes"], -x["total"], x["player"].lower()))

        seat_rows: List[Dict[str, Any]] = []
        for sid, v in seat_map.items():
            seat_rows.append({
                "seat_id": sid,
                "player": _norm_player(v.get("player", "")),
                "choice": _norm_choice(v.get("choice", "")),
                "ts": int(v.get("ts", 0)),
            })
        seat_rows.sort(key=lambda x: (-x["ts"], x["seat_id"]))

        return {
            "vote_id": vid,
            "rows": rows,
            "seat_rows": seat_rows,
            "total_yes": total_yes,
            "total_no": total_no,
            "total_votes": total_yes + total_no,
        }


def get_vote_ingest_defaults() -> Dict[str, str]:
    """
    Return default vote context for legacy uplinks that don't include vote_id/player.
    Current strategy:
    - vote_id: active vote id (fallback mvp_live)
    - player: first configured player in active vote (fallback Player A)
    """
    with _lock:
        vid = _norm_vote_id(vote_active_id)
        players = list(vote_players_by_id.get(vid, []))
        default_player = players[0] if players else "Player A"
        return {"vote_id": vid, "player": default_player}
