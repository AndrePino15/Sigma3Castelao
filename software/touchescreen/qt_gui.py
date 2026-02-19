import json
import time
import subprocess
import os
from dataclasses import dataclass
import requests

from PySide6.QtCore import Qt, QObject, Signal, QTimer, QPropertyAnimation, QEasingCurve
from PySide6.QtGui import QFont, QPixmap, QPainter, QIcon
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QLabel, QPushButton,
    QGridLayout, QVBoxLayout, QHBoxLayout, QMessageBox, QStackedWidget,
    QLineEdit, QSpinBox, QGraphicsDropShadowEffect, QFrame, QScrollArea, QSizePolicy
)

from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput
from PySide6.QtMultimediaWidgets import QVideoWidget
from PySide6.QtCore import QUrl


import paho.mqtt.client as mqtt


# ====== Config ======
BROKER_HOST = os.getenv("MQTT_HOST", "127.0.0.1").strip() or "127.0.0.1"
BROKER_PORT = int(os.getenv("MQTT_PORT", "1883"))
SEAT_ID = "A3-12"

TOPIC_TELE = f"stadium/seat/{SEAT_ID}/telemetry"
TOPIC_CMD  = f"stadium/seat/{SEAT_ID}/cmd"
TOPIC_ACK  = f"stadium/seat/{SEAT_ID}/ack"
TOPIC_SAFETY = "stadium/broadcast/safety"

API_FOOTBALL_BASE = "https://v3.football.api-sports.io"
API_FOOTBALL_KEY = os.getenv("API_FOOTBALL_KEY", "").strip()
_fixture_env = os.getenv("API_FIXTURE_ID", "").strip()
API_FIXTURE_ID = int(_fixture_env) if _fixture_env else 0
# Pull upstream slower, publish cache faster.
API_UPSTREAM_MS = 30000
API_CACHE_READ_MS = 3000
API_BOOST_UPSTREAM_MS = 8000
API_BOOST_HOLD_MS = 120000


@dataclass
class Telemetry:
    ts: float = 0.0
    mode: str = "IDLE"
    device_id: str = SEAT_ID
    rssi: int = 0
    metric: float = 0.0
    msg: str = ""


class MqttBridge(QObject):
    # Signals to UI thread
    sig_connected = Signal(bool)
    sig_telemetry = Signal(dict)
    sig_ack = Signal(dict)
    sig_safety = Signal(dict)

    def __init__(self):
        super().__init__()
        self.client = mqtt.Client(client_id=f"qt_gui_{SEAT_ID}", clean_session=True)
        self.client.on_connect = self._on_connect
        self.client.on_disconnect = self._on_disconnect
        self.client.on_message = self._on_message

    def start(self):
        self.client.connect(BROKER_HOST, BROKER_PORT, keepalive=60)
        self.client.loop_start()

    def stop(self):
        try:
            self.client.loop_stop()
            self.client.disconnect()
        except Exception:
            pass

    def publish_cmd(self, cmd: str, value=1, payload: dict | None = None):
        msg = {
            "ts": time.time(),
            "device_id": SEAT_ID,
            "cmd": cmd,
            "value": value
        }
        if payload is not None:
            msg["payload"] = payload
        self.client.publish(TOPIC_CMD, json.dumps(msg), qos=1)



    # ----- MQTT callbacks (background thread) -----
    def _on_connect(self, client, userdata, flags, rc):
        self.sig_connected.emit(True)
        client.subscribe(TOPIC_TELE, qos=0)
        client.subscribe(TOPIC_ACK, qos=1)
        client.subscribe(TOPIC_SAFETY, qos=1)

    def _on_disconnect(self, client, userdata, rc):
        self.sig_connected.emit(False)

    def _on_message(self, client, userdata, msg):
        try:
            data = json.loads(msg.payload.decode("utf-8"))
        except Exception:
            return

        if msg.topic == TOPIC_TELE:
            self.sig_telemetry.emit(data)
        elif msg.topic == TOPIC_ACK:
            self.sig_ack.emit(data)
        elif msg.topic == TOPIC_SAFETY:
            self.sig_safety.emit(data)
        elif msg.topic == "stadium/broadcast/replay":
            data = json.loads(msg.payload.decode())
            video_url = data.get("url")
            self.replay_page.play_video(video_url)
            self.stack.setCurrentWidget(self.replay_page)

class DragScrollArea(QScrollArea):
    # Enable click-and-drag scrolling for touch-style interaction.
    def __init__(self):
        super().__init__()
        self._dragging = False
        self._start_y = 0
        self._start_scroll = 0
        self.viewport().setCursor(Qt.OpenHandCursor)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._dragging = True
            self._start_y = int(event.position().y())
            self._start_scroll = self.verticalScrollBar().value()
            self.viewport().setCursor(Qt.ClosedHandCursor)
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._dragging:
            dy = int(event.position().y()) - self._start_y
            self.verticalScrollBar().setValue(self._start_scroll - dy)
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if self._dragging and event.button() == Qt.LeftButton:
            self._dragging = False
            self.viewport().setCursor(Qt.OpenHandCursor)
            event.accept()
            return
        super().mouseReleaseEvent(event)


class MatchStatRow(QWidget):
    def __init__(self, name: str):
        super().__init__()
        self.left_val = QLabel("0")
        self.right_val = QLabel("0")
        self.mid_name = QLabel(name)

        for n in (self.left_val, self.right_val):
            n.setAlignment(Qt.AlignCenter)
            n.setMinimumWidth(70)
            n.setStyleSheet(
                "background: rgba(3, 6, 40, 220);"
                "color: white;"
                "font: 700 24px 'Arial';"
                "border-radius: 10px;"
                "padding: 4px 8px;"
            )

        self.mid_name.setAlignment(Qt.AlignCenter)
        self.mid_name.setMinimumHeight(52)
        self.mid_name.setStyleSheet(
            "background: rgba(245,245,245,235);"
            "color: #111111;"
            "font: 700 21px 'Arial';"
            "border-radius: 8px;"
        )

        layout = QHBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        layout.addWidget(self.left_val, stretch=3)
        layout.addWidget(self.mid_name, stretch=8)
        layout.addWidget(self.right_val, stretch=3)
        self.setLayout(layout)

    def set_values(self, left, right):
        self.left_val.setText(self._normalize_stat_value(left))
        self.right_val.setText(self._normalize_stat_value(right))

    @staticmethod
    def _normalize_stat_value(v) -> str:
        if v is None:
            return "0"
        s = str(v).strip()
        if s == "" or s == "-":
            return "0"
        return s


class MatchInfoPanel(QWidget):
    REQUIRED_KEYS = ("home", "away", "score", "time", "event", "note")

    def __init__(self):
        super().__init__()
        self._default_stat_names = [
            "POSSESSION",
            "CORNERS",
            "SHOTS",
            "SHOTS ON TARGET",
            "BLOCKED SHOTS",
            "OFFSIDES",
            "FOULS",
            "YELLOW CARDS",
            "PASS SUCCESS",
            "GOALKEEPER SAVES",
        ]
        self._err = QLabel("")
        self._err.setWordWrap(True)
        self._err.setStyleSheet("color: #ffd2d2; font: 700 16px 'Arial';")

        self.home_name = QLabel("TEAM A")
        self.away_name = QLabel("TEAM B")
        self.event_name = QLabel("INFORMATION")
        self.score_label = QLabel("0-0")
        self.time_label = QLabel("--:--")
        self.note_label = QLabel("No note")

        self.home_name.setAlignment(Qt.AlignCenter)
        self.away_name.setAlignment(Qt.AlignCenter)
        for side_name in (self.home_name, self.away_name):
            side_name.setMinimumHeight(62)
            side_name.setStyleSheet(
                "background: rgba(3, 6, 40, 220);"
                "color: white;"
                "font: 700 28px 'Arial';"
                "border-radius: 12px;"
            )

        self.event_name.setAlignment(Qt.AlignCenter)
        self.event_name.setStyleSheet("color: white; font: 700 24px 'Arial';")
        self.score_label.setAlignment(Qt.AlignCenter)
        self.score_label.setStyleSheet("color: white; font: 700 64px 'Arial';")
        self.time_label.setAlignment(Qt.AlignCenter)
        self.time_label.setStyleSheet("color: #d7dfff; font: 700 20px 'Arial';")
        self.note_label.setAlignment(Qt.AlignCenter)
        self.note_label.setStyleSheet("color: #d7dfff; font: 600 16px 'Arial';")

        self.center_header = QFrame()
        self.center_header.setStyleSheet(
            "QFrame {"
            "background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #2b1462, stop:1 #122a76);"
            "border-radius: 16px;"
            "}"
        )
        center_header_layout = QVBoxLayout()
        center_header_layout.setContentsMargins(12, 8, 12, 10)
        center_header_layout.setSpacing(0)
        center_header_layout.addWidget(self.event_name)
        center_header_layout.addWidget(self.score_label)
        center_header_layout.addWidget(self.time_label)
        self.center_header.setLayout(center_header_layout)

        head_row = QHBoxLayout()
        head_row.setSpacing(12)
        head_row.addWidget(self.home_name, stretch=3)
        head_row.addWidget(self.center_header, stretch=6)
        head_row.addWidget(self.away_name, stretch=3)

        self.rows = []
        self.rows_box = QVBoxLayout()
        self.rows_box.setSpacing(10)
        for name in self._default_stat_names:
            row = MatchStatRow(name)
            self.rows.append(row)
            self.rows_box.addWidget(row)
        self.rows_box.addStretch(1)

        self.rows_container = QWidget()
        self.rows_container.setLayout(self.rows_box)
        self.rows_container.setStyleSheet("background: transparent;")

        self.rows_scroll = DragScrollArea()
        self.rows_scroll.setWidgetResizable(True)
        self.rows_scroll.setFrameShape(QFrame.NoFrame)
        self.rows_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.rows_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.rows_scroll.setWidget(self.rows_container)
        self.rows_scroll.setStyleSheet(
            "QScrollArea { background: transparent; }"
            "QScrollBar:vertical {"
            "  width: 10px;"
            "  background: rgba(255,255,255,30);"
            "  border-radius: 5px;"
            "}"
            "QScrollBar::handle:vertical {"
            "  background: rgba(255,255,255,130);"
            "  border-radius: 5px;"
            "  min-height: 24px;"
            "}"
            "QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0px; }"
        )

        root = QVBoxLayout()
        root.setContentsMargins(18, 18, 18, 18)
        root.setSpacing(14)
        root.addLayout(head_row)
        root.addWidget(self.note_label)
        root.addSpacing(2)
        root.addWidget(self.rows_scroll, stretch=1)
        root.addWidget(self._err)
        self.setLayout(root)

        self.setStyleSheet(
            "background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #2f0b5e, stop:1 #0b1758);"
            "border-radius: 18px;"
        )
        self.set_info_dict({})

    @classmethod
    def format_info_text(cls, d: dict) -> str:
        data = d if isinstance(d, dict) else {}
        defaults = {
            "home": "TBD",
            "away": "TBD",
            "score": "0 - 0",
            "time": "--:--",
            "event": "Unknown Event",
            "note": "No note",
        }
        for key in cls.REQUIRED_KEYS:
            val = data.get(key, defaults[key])
            if val is None or str(val).strip() == "":
                val = defaults[key]
            defaults[key] = str(val)
        return (
            f"Home:  {defaults['home']}\n"
            f"Away:  {defaults['away']}\n"
            f"Score: {defaults['score']}\n"
            f"Time:  {defaults['time']}\n"
            f"Event: {defaults['event']}\n"
            f"Note:  {defaults['note']}"
        )

    def set_info_dict(self, d: dict):
        data = d if isinstance(d, dict) else {}
        self._err.setText("")
        self.home_name.setText(str(data.get("home") or "TEAM A"))
        self.away_name.setText(str(data.get("away") or "TEAM B"))
        self.event_name.setText(str(data.get("event") or "INFORMATION"))
        self.score_label.setText(str(data.get("score") or "0-0"))
        self.time_label.setText(str(data.get("time") or "--:--"))
        self.note_label.setText(str(data.get("note") or "No note"))

        stats = self._extract_stats(data)
        for row, (name, left, right) in zip(self.rows, stats):
            row.mid_name.setText(str(name))
            row.set_values(left, right)

    def set_error(self, err: str):
        msg = err.strip() if isinstance(err, str) and err.strip() else "Unknown error"
        self._err.setText(f"Match info unavailable: {msg}")

    def _extract_stats(self, data: dict):
        # Prefer explicit "stats" payload from upstream; fallback to key-based mapping.
        incoming = data.get("stats")
        parsed = []
        if isinstance(incoming, list):
            for it in incoming:
                if isinstance(it, dict):
                    parsed.append(
                        (
                            str(it.get("name") or it.get("label") or "STAT"),
                            it.get("home", "0"),
                            it.get("away", "0"),
                        )
                    )
        elif isinstance(incoming, dict):
            for k, v in incoming.items():
                if isinstance(v, dict):
                    parsed.append((str(k), v.get("home", "0"), v.get("away", "0")))
        if not parsed:
            parsed = [
                ("POSSESSION", data.get("home_possession", "0"), data.get("away_possession", "0")),
                ("CORNERS", data.get("home_corners", "0"), data.get("away_corners", "0")),
                ("SHOTS", data.get("home_shots", "0"), data.get("away_shots", "0")),
                ("SHOTS ON TARGET", data.get("home_shots_on_target", "0"), data.get("away_shots_on_target", "0")),
                ("BLOCKED SHOTS", data.get("home_blocked", "0"), data.get("away_blocked", "0")),
                ("OFFSIDES", data.get("home_offsides", "0"), data.get("away_offsides", "0")),
                ("FOULS", data.get("home_fouls", "0"), data.get("away_fouls", "0")),
                ("YELLOW CARDS", data.get("home_yellow", "0"), data.get("away_yellow", "0")),
                ("PASS SUCCESS", data.get("home_pass_success", "0"), data.get("away_pass_success", "0")),
                ("GOALKEEPER SAVES", data.get("home_saves", "0"), data.get("away_saves", "0")),
            ]
        while len(parsed) < len(self.rows):
            parsed.append((self._default_stat_names[len(parsed)], "0", "0"))
        return parsed[:len(self.rows)]


class HomePage(QWidget):
    sig_goto = Signal(str)  # "replay"/"info"/"order"/"admin"

    def __init__(self):
        super().__init__()
        self._tap = 0
        self._tap_timer = QTimer(self)
        self._tap_timer.setInterval(1200)
        self._tap_timer.timeout.connect(self._reset_tap)

        self._bg = QPixmap("assets/background.png")
        self._menu_collapsed_w = 76
        self._menu_expanded_w = 300
        self._menu_expanded = False
        self._menu_inner_margin = 10

        self.title = QLabel("Home Page")
        self.title.setFont(QFont("Segoe Script", 34, QFont.Bold))
        self.title.setStyleSheet(
            "color: #f9f3d1;"
            "letter-spacing: 2px;"
        )
        title_shadow = QGraphicsDropShadowEffect(self)
        title_shadow.setBlurRadius(14)
        title_shadow.setOffset(2, 2)
        title_shadow.setColor(Qt.black)
        self.title.setGraphicsEffect(title_shadow)
        self.title.setAlignment(Qt.AlignLeft | Qt.AlignTop)
        self.title.mousePressEvent = self._title_clicked

        self.match_panel = MatchInfoPanel()

        self.btn_menu = QPushButton()
        self.btn_menu.setFixedSize(56, 56)
        self.btn_menu.setCursor(Qt.PointingHandCursor)
        self.btn_menu.setFlat(True)
        self.btn_menu.setFocusPolicy(Qt.NoFocus)
        menu_icon = QPixmap("assets/menu.png")
        if menu_icon.isNull():
            menu_icon = QPixmap("assets/MENU.png")
        if not menu_icon.isNull():
            self.btn_menu.setIcon(QIcon(menu_icon))
            self.btn_menu.setIconSize(self.btn_menu.size() * 0.7)
        self.btn_menu.setStyleSheet(
            "QPushButton {"
            "  background: transparent;"
            "  border: none;"
            "}"
            "QPushButton:pressed {"
            "  background: rgba(255,255,255,40);"
            "  border: none;"
            "  border-radius: 10px;"
            "}"
        )
        self.btn_menu.clicked.connect(self._toggle_menu)

        self.btn_replay = QPushButton("REPLAY")
        self.btn_order = QPushButton("ORDER")
        btn_style = (
            "QPushButton {"
            "  color: white;"
            "  background: transparent;"
            "  border: 2px solid rgba(255,255,255,200);"
            "  border-radius: 16px;"
            "  padding: 14px 26px;"
            "}"
            "QPushButton:hover { border-color: rgba(255,255,255,255); }"
            "QPushButton:pressed { background: rgba(255,255,255,35); }"
        )
        for btn in (self.btn_replay, self.btn_order):
            btn.setMinimumHeight(250)
            btn.setFont(QFont("Arial", 14, QFont.Bold))
            btn.setStyleSheet(btn_style)
            btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
            btn.hide()

        self.btn_replay.clicked.connect(lambda: self.sig_goto.emit("replay"))
        self.btn_order.clicked.connect(lambda: self.sig_goto.emit("order"))

        self.menu_panel = QWidget()
        self.menu_panel.setStyleSheet(
            "background-color: rgba(0,0,0,85);"
            "border: 1px solid rgba(255,255,255,80);"
            "border-radius: 18px;"
        )
        self.menu_panel.setMaximumWidth(self._menu_collapsed_w)
        self.menu_panel.setMinimumWidth(0)

        menu_layout = QVBoxLayout()
        menu_layout.setContentsMargins(10, 10, 10, 10)
        menu_layout.setSpacing(14)
        menu_layout.addWidget(self.btn_menu, alignment=Qt.AlignTop | Qt.AlignLeft)
        menu_layout.addSpacing(10)
        menu_layout.addWidget(self.btn_replay, stretch=1)
        menu_layout.addWidget(self.btn_order, stretch=1)
        menu_layout.addStretch(0)
        self.menu_panel.setLayout(menu_layout)

        self._menu_anim = QPropertyAnimation(self.menu_panel, b"maximumWidth", self)
        self._menu_anim.setDuration(220)
        self._menu_anim.setEasingCurve(QEasingCurve.InOutCubic)
        self._menu_anim.finished.connect(self._on_menu_anim_finished)
        self._menu_anim.valueChanged.connect(self._on_menu_width_changed)
        self._update_menu_button_width(self.menu_panel.maximumWidth())

        left_region = QWidget()
        left_layout = QHBoxLayout()
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.addWidget(self.menu_panel, alignment=Qt.AlignTop | Qt.AlignLeft)
        left_layout.addStretch(1)
        left_region.setLayout(left_layout)

        right_region = QWidget()
        right_layout = QVBoxLayout()
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(10)
        right_layout.addWidget(self.match_panel, stretch=1)
        right_region.setLayout(right_layout)

        content_row = QHBoxLayout()
        content_row.setContentsMargins(0, 0, 0, 0)
        content_row.setSpacing(22)
        content_row.addWidget(left_region, stretch=1)
        content_row.addWidget(right_region, stretch=3)

        root = QVBoxLayout()
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        root.addWidget(self.title, alignment=Qt.AlignTop | Qt.AlignHCenter)
        root.addLayout(content_row, stretch=1)
        self.setLayout(root)

    def paintEvent(self, event):
        painter = QPainter(self)
        if self._bg.isNull():
            painter.fillRect(self.rect(), Qt.black)
        else:
            painter.drawPixmap(self.rect(), self._bg)
        super().paintEvent(event)

    def _toggle_menu(self):
        self._menu_anim.stop()
        expanding = not self._menu_expanded
        self._menu_expanded = expanding

        if expanding:
            self.btn_replay.show()
            self.btn_order.show()
            end_w = self._calc_menu_expanded_width()
        else:
            end_w = self._menu_collapsed_w

        self._menu_anim.setStartValue(self.menu_panel.maximumWidth())
        self._menu_anim.setEndValue(end_w)
        self._menu_anim.start()

    def _on_menu_anim_finished(self):
        if not self._menu_expanded:
            self.btn_replay.hide()
            self.btn_order.hide()
        self._update_menu_button_width(self.menu_panel.maximumWidth())

    def _on_menu_width_changed(self, value):
        # Keep button width visually in sync while panel animates.
        self._update_menu_button_width(int(value))

    def resizeEvent(self, event):
        self._menu_expanded_w = self._calc_menu_expanded_width()
        if self._menu_expanded:
            self.menu_panel.setMaximumWidth(self._menu_expanded_w)
        self._update_menu_button_width(self.menu_panel.maximumWidth())
        super().resizeEvent(event)

    def _calc_menu_expanded_width(self) -> int:
        target = int(self.width() * 0.32)
        return max(320, target)

    def _update_menu_button_width(self, panel_width: int):
        # Make audience buttons narrower than panel width for visual breathing room.
        usable = max(80, int(panel_width * 0.75) - self._menu_inner_margin * 2)
        for btn in (self.btn_replay, self.btn_order):
            btn.setMinimumWidth(usable)
            btn.setMaximumWidth(usable)

    def _title_clicked(self, event):
        self._tap += 1
        if not self._tap_timer.isActive():
            self._tap_timer.start()
        if self._tap >= 5:
            self._reset_tap()
            self.sig_goto.emit("admin")

    def _reset_tap(self):
        self._tap = 0
        self._tap_timer.stop()

class BackButton(QPushButton):
    def __init__(self):
        super().__init__()
        self.setFixedSize(64, 64)
        self.setFlat(True)
        self.setFocusPolicy(Qt.NoFocus)

        pm = QPixmap("assets/back.png")
        if not pm.isNull():
            self.setIcon(QIcon(pm))
            self.setIconSize(self.size() * 0.65)

        # Default: icon only (no border / no background).
        # Pressed: subtle translucent feedback without border.
        self.setStyleSheet(
            "QPushButton {"
            "  background: transparent;"
            "  border: none;"
            "}"
            "QPushButton:pressed {"
            "  background: rgba(255,255,255,25);"
            "  border-radius: 10px;"
            "  border: none;"
            "}"
        )



class BaseSubPage(QWidget):
    sig_back = Signal()

    def __init__(self, title_text: str):
        super().__init__()
        self._use_bg = False
        self._bg = QPixmap("assets/background.png")
        self.title = QLabel(title_text)
        self.title.setFont(QFont("Arial", 22, QFont.Bold))
        self.title.setStyleSheet("color: white;")

        self.btn_back = BackButton()
        self.btn_back.clicked.connect(self.sig_back.emit)

        root = QVBoxLayout()
        root.setContentsMargins(24, 24, 24, 24)
        root.setSpacing(16)
        root.addWidget(self.title)

        self.content = QVBoxLayout()
        root.addLayout(self.content)
        root.addStretch(1)

        bottom = QHBoxLayout()
        bottom.addWidget(self.btn_back, alignment=Qt.AlignLeft | Qt.AlignBottom)
        bottom.addStretch(1)
        root.addLayout(bottom)

        self.setLayout(root)

    def set_background_enabled(self, enabled: bool):
        self._use_bg = bool(enabled)
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        if self._use_bg and not self._bg.isNull():
            painter.drawPixmap(self.rect(), self._bg)
        else:
            painter.fillRect(self.rect(), Qt.black)
        super().paintEvent(event)

class ReplayPage(BaseSubPage):
    def __init__(self):
        super().__init__("Replay")
        self.set_background_enabled(True)

        self.btn_last = QPushButton("Last Highlight")
        self.btn_goal = QPushButton("Last Goal")
        self.btn_top  = QPushButton("Top Moments")

        for b in [self.btn_last, self.btn_goal, self.btn_top]:
            b.setMinimumHeight(90)
            b.setFont(QFont("Arial", 16, QFont.Bold))
            b.setStyleSheet(
                "QPushButton { color:white; background:#2a2a2a; border-radius:18px; }"
                "QPushButton:pressed { background:#3a3a3a; }"
            )

        self.content.addWidget(self.btn_last)
        self.content.addWidget(self.btn_goal)
        self.content.addWidget(self.btn_top)
        self.content.addSpacing(20)
        
        self.video_widget = QVideoWidget()
        self.player = QMediaPlayer()
        self.audio = QAudioOutput()
        self.player.setAudioOutput(self.audio)
        self.player.setVideoOutput(self.video_widget)
        

        video_row = QHBoxLayout()
        video_row.addStretch(1)
        video_row.addWidget(self.video_widget)
        video_row.addStretch(1)

        self.content.addLayout(video_row)

        self.btn_last.clicked.connect(lambda: self.play_video("highlight.mp4"))
        self.btn_goal.clicked.connect(lambda: self.play_video("goal.mp4"))
        self.btn_top.clicked.connect(lambda: self.play_video("moment.mp4"))

    def play_video(self,filename):
        from PySide6.QtCore import QUrl
        from PySide6.QtWidgets import QWidget, QVBoxLayout
        import os

        path = os.path.abspath(filename)
        self.video_widget.hide()

        self.fullscreen_window = QWidget()
        self.fullscreen_window.setWindowFlag(Qt.Window)
        self.fullscreen_window.setWindowState(Qt.WindowFullScreen)
        layout = QVBoxLayout()
        self.fullscreen_video = QVideoWidget()
        layout.addWidget(self.fullscreen_video)
        self.fullscreen_window.setLayout(layout)
        
        self.player.setVideoOutput(self.fullscreen_video)
        self.player.setSource(QUrl.fromLocalFile(path))
        self.player.play()
        self.fullscreen_video.mousePressEvent = self.exit_fullscreen
        self.fullscreen_window.show()
        
    def exit_fullscreen(self, event=None):
        self.player.stop()
        if hasattr(self, "fullscreen_window"):
            self.fullscreen_window.close()
        
        self.player.setVideoOutput(self.video_widget)

class InfoPage(BaseSubPage):
    def __init__(self):
        super().__init__("Match Info")
        self.lbl = QLabel("Waiting for match info...")
        self.lbl.setFont(QFont("Arial", 16))
        self.lbl.setStyleSheet("color: white;")
        self.lbl.setWordWrap(True)
        self.content.addWidget(self.lbl)

    def set_info(self, text: str):
        self.lbl.setText(text)

class OrderPage(BaseSubPage):
    def __init__(self):
        super().__init__("Order")
        self.set_background_enabled(True)

        self.item = QLineEdit()
        self.item.setPlaceholderText("Item (e.g., Cola)")
        self.qty = QSpinBox()
        self.qty.setRange(1, 10)
        self.note = QLineEdit()
        self.note.setPlaceholderText("Note (e.g., no ice)")

        for w in [self.item, self.note]:
            w.setMinimumHeight(50)
            w.setFont(QFont("Arial", 14))

        self.qty.setMinimumHeight(50)
        self.qty.setFont(QFont("Arial", 14))

        self.btn_submit = QPushButton("Submit Order")
        self.btn_kb = QPushButton("Keyboard")
        self.btn_kb.setMinimumHeight(60)
        self.btn_kb.setFont(QFont("Arial", 14, QFont.Bold))
        self.btn_kb.setStyleSheet(
            "QPushButton { color:white; background:#2a2a2a; border-radius:18px; }"
            "QPushButton:pressed { background:#3a3a3a; }"
        )
        self.btn_submit.setMinimumHeight(70)
        self.btn_submit.setFont(QFont("Arial", 16, QFont.Bold))
        self.btn_submit.setStyleSheet(
            "QPushButton { color:white; background:#2a2a2a; border-radius:18px; }"
            "QPushButton:pressed { background:#3a3a3a; }"
        )

        lab1 = QLabel("Item:")
        lab2 = QLabel("Quantity:")
        lab3 = QLabel("Note:")
        for lab in [lab1, lab2, lab3]:
            lab.setStyleSheet("color: white;")
            lab.setFont(QFont("Arial", 12, QFont.Bold))

        self.content.addWidget(lab1)
        self.content.addWidget(self.item)
        self.content.addWidget(lab2)
        self.content.addWidget(self.qty)
        self.content.addWidget(lab3)
        self.content.addWidget(self.note)
        self.content.addSpacing(10)
        self.content.addWidget(self.btn_kb)
        self.content.addWidget(self.btn_submit)


class AdminPage(QWidget):
    def __init__(self):
        super().__init__()

        title = QLabel("Touchscreen Dashboard (Qt + MQTT)")
        title.setFont(QFont("Arial", 18, QFont.Bold))

        # 6 fields
        self.btn_back_home = QPushButton("Back to Home")
        self.btn_back_home.setMinimumHeight(50)
        self.btn_back_home.setFont(QFont("Arial", 12, QFont.Bold))
        self.lbl_conn = QLabel("DISCONNECTED")
        self.lbl_last = QLabel("-")
        self.lbl_mode = QLabel("-")
        self.lbl_dev  = QLabel(SEAT_ID)
        self.lbl_msg  = QLabel("-")
        self.lbl_metric = QLabel("-")

        for w in [self.lbl_conn, self.lbl_last, self.lbl_mode, self.lbl_dev, self.lbl_msg, self.lbl_metric]:
            w.setFont(QFont("Arial", 14))
            w.setWordWrap(True)

        grid = QGridLayout()
        grid.setHorizontalSpacing(18)
        grid.setVerticalSpacing(12)

        def add_row(r, name, widget):
            lab = QLabel(name)
            lab.setFont(QFont("Arial", 12, QFont.Bold))
            grid.addWidget(lab, r, 0, alignment=Qt.AlignTop)
            grid.addWidget(widget, r, 1)

        add_row(0, "Connection", self.lbl_conn)
        add_row(1, "Last Update", self.lbl_last)
        add_row(2, "Mode", self.lbl_mode)
        add_row(3, "Device ID", self.lbl_dev)
        add_row(4, "Message/Alert", self.lbl_msg)
        add_row(5, "Metric (RSSI/Score)", self.lbl_metric)

        layout = QVBoxLayout()
        layout.addWidget(title)
        layout.addWidget(self.btn_back_home)
        layout.addSpacing(10)
        layout.addLayout(grid)
        layout.addStretch(1)
        self.setLayout(layout)

    def set_connection(self, ok: bool):
        if ok:
            self.lbl_conn.setText("CONNECTED")
            self.lbl_conn.setStyleSheet("color: green; font-weight: bold;")
        else:
            self.lbl_conn.setText("DISCONNECTED")
            self.lbl_conn.setStyleSheet("color: red; font-weight: bold;")

    def set_last_update(self, text: str, color: str = "black"):
        self.lbl_last.setText(text)
        self.lbl_last.setStyleSheet(f"color: {color};")

    def set_telemetry(self, d: dict):
        self.lbl_mode.setText(str(d.get("mode", "-")))
        self.lbl_dev.setText(str(d.get("device_id", SEAT_ID)))
        self.lbl_msg.setText(str(d.get("msg", "-")))

        # show both RSSI + metric in one line
        rssi = d.get("rssi", "-")
        metric = d.get("metric", "-")
        self.lbl_metric.setText(f"RSSI {rssi} dBm | Metric {metric}")


class SafetyPage(QWidget):
    def __init__(self):
        super().__init__()
        self.title = QLabel("SAFETY MODE")
        self.title.setFont(QFont("Arial", 28, QFont.Bold))
        self.title.setStyleSheet("color: white;")

        self.msg = QLabel("-")
        self.msg.setFont(QFont("Arial", 20, QFont.Bold))
        self.msg.setStyleSheet("color: white;")
        self.msg.setWordWrap(True)

        self.btn_ack = QPushButton("ACKNOWLEDGE")
        self.btn_ack.setMinimumHeight(70)
        self.btn_ack.setFont(QFont("Arial", 16, QFont.Bold))

        layout = QVBoxLayout()
        layout.addWidget(self.title)
        layout.addWidget(self.msg)
        layout.addStretch(1)
        layout.addWidget(self.btn_ack)

        self.setLayout(layout)
        self.setStyleSheet("background-color: #b00020; padding: 20px;")

    def set_message(self, d: dict):
        level = d.get("level", "INFO")
        msg = d.get("msg", "")
        self.msg.setText(f"[{level}] {msg}")


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Screen GUI (Qt + MQTT)")
        self.resize(1280, 720)  # match your display resolution

        self.bridge = MqttBridge()
        self.tele = Telemetry()
        self.last_rx_ms = 0

        self.stack = QStackedWidget()

        self.page_home = HomePage()
        self.page_replay = ReplayPage()
        self.page_info = InfoPage()
        self.page_order = OrderPage()
        self.page_admin = AdminPage()
        self.page_safety = SafetyPage()
        self._match_info_keys = set(MatchInfoPanel.REQUIRED_KEYS)
        self._has_api_match_info = False
        self._cached_match_info = None
        self._cached_match_error = ""
        self._cached_info_ver = 0
        self._published_info_ver = -1
        self._boost_until_ms = 0
        self._last_score_key = ""

        self.stack.addWidget(self.page_home)
        self.stack.addWidget(self.page_replay)
        self.stack.addWidget(self.page_info)
        self.stack.addWidget(self.page_order)
        self.stack.addWidget(self.page_admin)
        self.stack.addWidget(self.page_safety)
        self._apply_match_info({})

        self.setCentralWidget(self.stack)

        # Home navigation
        self.page_home.sig_goto.connect(self._goto_page)

        # Admin back
        self.page_admin.btn_back_home.clicked.connect(lambda: self._goto_page("home"))

        # Subpages back (bottom-left back button)
        self.page_replay.sig_back.connect(lambda: self._goto_page("home"))
        self.page_info.sig_back.connect(lambda: self._goto_page("home"))
        self.page_order.sig_back.connect(lambda: self._goto_page("home"))

        # Order submit
        self.page_order.btn_submit.clicked.connect(self._submit_order)
        self.page_order.btn_kb.clicked.connect(self._open_keyboard)

        # Safety ack (先留着，不用管安全逻辑也不影响)
        self.page_safety.btn_ack.clicked.connect(self._ack_safety)

        # MQTT -> UI signals
        self.bridge.sig_connected.connect(self._on_connected)
        self.bridge.sig_telemetry.connect(self._on_telemetry)
        self.bridge.sig_ack.connect(self._on_ack)
        self.bridge.sig_safety.connect(self._on_safety)

        # Heartbeat timer for stale detection
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._stale_check)
        self.timer.start(200)

        # API middle-layer behavior:
        # 1) pull third-party API into local cache (slow)
        # 2) publish cached data to UI (fast)
        self.api_upstream_timer = QTimer(self)
        self.api_upstream_timer.timeout.connect(self._update_cache_from_api)
        self.api_upstream_timer.start(API_UPSTREAM_MS)
        QTimer.singleShot(200, self._update_cache_from_api)

        self.api_cache_timer = QTimer(self)
        self.api_cache_timer.timeout.connect(self._publish_cached_match_info)
        self.api_cache_timer.start(API_CACHE_READ_MS)

        self.bridge.start()

    def closeEvent(self, event):
        self.bridge.stop()
        super().closeEvent(event)

    def _goto_page(self, name: str):
        if name == "home":
            self.stack.setCurrentWidget(self.page_home)
        elif name == "replay":
            self.stack.setCurrentWidget(self.page_replay)
        elif name == "info":
            self.stack.setCurrentWidget(self.page_info)
        elif name == "order":
            self.stack.setCurrentWidget(self.page_order)
        elif name == "admin":
            self.stack.setCurrentWidget(self.page_admin)
        else:
            QMessageBox.information(self, "TODO", f"Unknown page: {name}")


    def _on_connected(self, ok: bool):
        self.page_admin.set_connection(ok)

    def _on_telemetry(self, d: dict):
        self.last_rx_ms = int(time.time() * 1000)
        self.page_admin.set_telemetry(d)
        self.page_admin.set_last_update(time.strftime("%H:%M:%S"), "green")

        if any(k in d for k in self._match_info_keys):
            self._apply_match_info(d)

        # If telemetry says SAFETY, also switch (optional)
        if str(d.get("mode", "")).upper() == "SAFETY":
            self._switch_to_safety({"level": "CRITICAL", "msg": d.get("msg", "Safety mode")})

    def _on_ack(self, d: dict):
        ref = d.get("ref_cmd", "")
        ok = d.get("ok", False)
        msg = d.get("msg", "")
        QMessageBox.information(self, "ACK", f"ok={ok}\nref_cmd={ref}\nmsg={msg}")

    def _on_safety(self, d: dict):
        mode = str(d.get("mode", "")).upper()
        if mode == "SAFETY":
            self._switch_to_safety(d)
        elif mode in ["NORMAL", "CLEAR", "CLEARED"]:
            self.stack.setCurrentWidget(self.page_admin)

    def _switch_to_safety(self, d: dict):
        self.page_safety.set_message(d)
        self.stack.setCurrentWidget(self.page_safety)

    def _ack_safety(self):
        # Send an ACK command; keep UI policy simple: go back to dashboard
        self.bridge.publish_cmd("SAFETY_ACK", 1)
        self.stack.setCurrentWidget(self.page_admin)

    def _submit_order(self):
        payload = {
            "item": self.page_order.item.text().strip(),
            "qty": int(self.page_order.qty.value()),
            "note": self.page_order.note.text().strip()
        }
        self.bridge.publish_cmd("ORDER", 1, payload=payload)
        QMessageBox.information(self, "Order", "Order sent!")

    def _open_keyboard(self):
        # Windows touch keyboard
        try:
            subprocess.Popen(["cmd", "/c", "start", "osk"])
        except Exception as e:
            QMessageBox.warning(self, "Keyboard", f"Failed to open keyboard: {e}")

    def _stale_check(self):
        if self.last_rx_ms == 0:
            return
        dt = int(time.time() * 1000) - self.last_rx_ms
        if dt > 3000:
            self.page_admin.set_last_update("STALE >3s", "red")
        elif dt > 1000:
            self.page_admin.set_last_update("STALE >1s", "orange")

    def _update_cache_from_api(self):
        # This is the only place that hits third-party football API.
        try:
            info = self._fetch_api_match_info(API_FIXTURE_ID)
            self._has_api_match_info = True
            self._cached_match_error = ""
            self._cached_match_info = info
            self._cached_info_ver += 1
            self._detect_goal_and_boost(info)
        except Exception as e:
            self._cached_match_error = str(e)
            if not self._has_api_match_info:
                self.set_match_info_error(self._cached_match_error)
        finally:
            self._refresh_upstream_interval()

    def _publish_cached_match_info(self):
        # UI refresh from cache only; avoids extra third-party requests.
        if self._cached_match_info is not None:
            if self._published_info_ver != self._cached_info_ver:
                self.set_match_info(self._cached_match_info)
                self._published_info_ver = self._cached_info_ver
            return
        if self._cached_match_error:
            self.set_match_info_error(self._cached_match_error)

    def _detect_goal_and_boost(self, info: dict):
        # Score change -> temporary higher upstream pull frequency.
        score = str(info.get("score", "")).strip()
        if not score:
            return
        if self._last_score_key and self._last_score_key != score:
            now_ms = int(time.time() * 1000)
            self._boost_until_ms = now_ms + API_BOOST_HOLD_MS
        self._last_score_key = score

    def _refresh_upstream_interval(self):
        now_ms = int(time.time() * 1000)
        target = API_BOOST_UPSTREAM_MS if now_ms < self._boost_until_ms else API_UPSTREAM_MS
        if self.api_upstream_timer.interval() != target:
            self.api_upstream_timer.setInterval(target)

    def _fetch_api_match_info(self, fixture_id: int) -> dict:
        # Build one normalized info dict for both Home match panel and Info page.
        if not API_FOOTBALL_KEY:
            raise RuntimeError("Missing API_FOOTBALL_KEY environment variable")
        if fixture_id <= 0:
            raise RuntimeError("Missing API_FIXTURE_ID environment variable")
        headers = {"x-apisports-key": API_FOOTBALL_KEY}

        r1 = requests.get(
            f"{API_FOOTBALL_BASE}/fixtures",
            params={"id": fixture_id},
            headers=headers,
            timeout=8,
        )
        r1.raise_for_status()
        j1 = r1.json()
        if j1.get("errors"):
            raise RuntimeError(str(j1.get("errors")))
        if not j1.get("response"):
            raise RuntimeError("fixture not found")

        match = j1["response"][0]
        home = match.get("teams", {}).get("home", {})
        away = match.get("teams", {}).get("away", {})
        fixture = match.get("fixture", {})
        status = fixture.get("status", {})
        league = match.get("league", {})
        goals = match.get("goals", {})

        home_id = home.get("id")
        away_id = away.get("id")
        home_name = self._api_safe(home.get("name"), "TEAM A")
        away_name = self._api_safe(away.get("name"), "TEAM B")
        score = f"{self._api_safe(goals.get('home'), '0')}-{self._api_safe(goals.get('away'), '0')}"
        elapsed = status.get("elapsed")
        short = self._api_safe(status.get("short"), "--:--")
        time_text = str(elapsed) if elapsed is not None else short
        event = self._api_safe(league.get("name"), "INFORMATION")
        note = self._api_safe(status.get("long"), "Live")

        r2 = requests.get(
            f"{API_FOOTBALL_BASE}/fixtures/statistics",
            params={"fixture": fixture_id},
            headers=headers,
            timeout=8,
        )
        r2.raise_for_status()
        j2 = r2.json()
        if j2.get("errors"):
            raise RuntimeError(str(j2.get("errors")))

        home_stats = []
        away_stats = []
        for team_block in j2.get("response", []):
            tid = team_block.get("team", {}).get("id")
            if tid == home_id:
                home_stats = team_block.get("statistics", [])
            elif tid == away_id:
                away_stats = team_block.get("statistics", [])

        def pair(label: str, api_name) -> dict:
            return {
                "name": label,
                "home": self._api_find_stat(home_stats, api_name),
                "away": self._api_find_stat(away_stats, api_name),
            }

        return {
            "home": home_name,
            "away": away_name,
            "score": score,
            "time": time_text,
            "event": event,
            "note": note,
            "stats": [
                pair("POSSESSION", "Ball Possession"),
                pair("CORNERS", "Corner Kicks"),
                pair("SHOTS", "Total Shots"),
                pair("SHOTS ON TARGET", "Shots on Goal"),
                pair("BLOCKED SHOTS", "Blocked Shots"),
                pair("OFFSIDES", "Offsides"),
                pair("FOULS", "Fouls"),
                pair("YELLOW CARDS", ["Yellow Cards", "Yellow Card"]),
                pair("PASS SUCCESS", "Passes %"),
                pair("GOALKEEPER SAVES", "Goalkeeper Saves"),
            ],
        }

    @staticmethod
    def _api_safe(value, default="-") -> str:
        return default if value is None or str(value).strip() == "" else str(value)

    @classmethod
    def _api_find_stat(cls, stats_list: list, stat_name) -> str:
        names = stat_name if isinstance(stat_name, (list, tuple, set)) else [stat_name]
        normalized = {str(n).strip().lower() for n in names}
        for s in stats_list:
            if not isinstance(s, dict):
                continue
            stype = str(s.get("type", "")).strip().lower()
            if stype in normalized:
                return cls._api_safe(s.get("value"), "-")
        return "-"

    def _apply_match_info(self, d: dict):
        self.page_home.match_panel.set_info_dict(d)
        self.page_info.set_info(MatchInfoPanel.format_info_text(d))

    def set_match_info(self, d: dict):
        self._apply_match_info(d)

    def set_match_info_error(self, err: str):
        self.page_home.match_panel.set_error(err)
        msg = err.strip() if isinstance(err, str) and err.strip() else "Unknown error"
        self.page_info.set_info(f"Match info unavailable.\n{msg}")


def main():
    app = QApplication([])
    w = MainWindow()
    w.show()
    app.exec()


if __name__ == "__main__":
    main()
