import canbus.protocol as protocol
from canbus.interface import CanInterface
from app.mqtt_client import MqttClient, MqttEvent
from app.mqtt_topics import control_topic, emergency_topic, led_topic, status_topic
from canbus.types import MessageTypes, OperationMode

import can
from typing import Any, Dict, Optional, List, Tuple
import time

class Bridge:
    """
    Section Controller bridge between MQTT (Wi-Fi) and CAN (seat bus).
    - Consumes queued MQTT events (from MqttClient)
    - Consumes queued CAN frames (from CanInterface)
    - Translates MQTT -> CAN commands
    - Forwards CAN -> MQTT status
    """
    def __init__(self, section_id: int,
                 broker_host: str,
                 broker_port: int = 1883,
                 can_channel: str = "can0",
                 can_bustype: str = "socketcan") -> None:
        
        self.section_id = section_id
        self.mode = OperationMode.NORMAL

        # Transport objects created in the constructor
        self.mqtt: Optional[MqttClient] = None
        self.can: Optional[CanInterface] =None

        # internal variables configuration
        self.broker_host = broker_host
        self.broker_port = broker_port 
        self.can_channel = can_channel
        self.can_bustype = can_bustype

        # The int inside each tupple defines the QoS for the subscription to that topic, which is a parameter 
        # from the MQTT protocol itself. 
        # QoS: emergency/control = 1 (more reliable), LED = 0 (best-effort)
        self.subscriptions: list[tuple[str, int]] = [(control_topic(self.section_id), 0),
                                              (led_topic(self.section_id), 0), 
                                              (emergency_topic(self.section_id), 1)]
        
        # Where this controller publishes aggregated status
        self.status_topic = status_topic(self.section_id)
        # simple run control
        self._running = False

# ================Methods for starting and stoping the controller================

    def start(self) -> None:
        '''
        Docstring for start
        
        This method is required to be called inside main.py to initialise the controller and both the MQTT Client and CAN bus.

        Its main functionalities are: connecting MQTT, starting CAN RX threads and apply CAN filters.
        '''
        # Create MQTT client
        self.mqtt = MqttClient(broker_host=self.broker_host,
                               broker_port=self.broker_port,
                               client_id=f"section-{self.section_id}",
                               keepalive=120,
                               rx_maxsize=256)

        # Create CAN interface
        self.can = CanInterface(channel=self.can_channel,
                                bustype=self.can_bustype,
                                rx_maxsize=256)
        
        # Connect MQTT
        connection_success = self.mqtt.connect(timeout=5.0)
        if not connection_success:
            # For now, we don't crash; we go DEGRADED and keep CAN running.
            self.mode = OperationMode.DEGRADED
            print(f"Connenction to {self.broker_host}:{self.broker_port} FAILED.")
        else:
            self.mqtt.subscribe(self.subscriptions)
            print(f"Successfully subscribed to {control_topic(self.section_id)}.")
            print(f"Successfully subscribed to {led_topic(self.section_id)}.")
            print(f"Successfully subscribed to {emergency_topic(self.section_id)}.")

        # Apply CAN filters to reduce load and seat->ctrl status range plus emergency/broadcast IDs
        filters = [
            {"can_id": protocol.SEAT_TO_CTRL_BASE, "can_mask": 0x700, "extended": False},
            {"can_id": protocol.EMERGENCY_ID, "can_mask": 0x7FF, "extended": False},
            {"can_id": protocol.BROADCAST_CMD_ID, "can_mask": 0x7FF, "extended": False},
        ]
        self.can.set_filters(filters)

        # Start CAN RX thread (enqueues to self.can.rx_queue)
        self.can.start_rx(timeout=1.0)

        self._running = True

    def stop(self) -> None:
        """
        This method stops loops and handles shutdown transports cleanly
        """
        self._running = False

        if self.mqtt is not None:
            self.mqtt.disconnect()
            self.mqtt = None

        if self.can is not None:
            self.can.close()
            self.can = None

# ================Methods for handling of the MQTT Client and CAN Bus================

    def mqtt_handle(self, event: MqttEvent) -> None:
        """
        This method handles one MQTT event: translate to CAN and/or update mode.
        """
        if self.can is None:
            return

        topic = event.topic
        payload = event.payload or {}

        # Emergency topic is global
        if topic == emergency_topic():
            # Enter safety mode immediately
            self.mode = OperationMode.SAFETY

            # You can decide what CAN message represents emergency.
            # For now: broadcast an EMERGENCY message type on EMERGENCY_ID.
            msg = can.Message(
                arbitration_id=protocol.EMERGENCY_ID,
                data=[MessageTypes.EMERGENCY, 1, 0, 0, 0, 0, 0, 0],
                is_extended_id=False,
            )
            self.can.send(msg)
            return

        # I should take a look at this LED implementation to make sure it agrees with what is happening with the server. 
        # Shouldn't be too much of a problem
        # Section specific topics
        if topic == led_topic(self.section_id):
            # Ignore LED commands in SAFETY mode
            if self.mode == OperationMode.SAFETY:
                return

            # Expect: {"seat": int, "rgb": [r,g,b]}
            seat = payload.get("seat")
            rgb = payload.get("rgb")

            if not isinstance(seat, int):
                return
            if (
                not isinstance(rgb, list)
                or len(rgb) != 3
                or not all(isinstance(x, int) for x in rgb)
            ):
                return

            r, g, b = rgb
            msg = protocol.encode_led_set(seat=seat, r=r, g=g, b=b)
            self.can.send(msg)
            return

        if topic == control_topic(self.section_id):
            # Basic control schema examples:
            # {"cmd": "set_mode", "mode": "NORMAL"} or {"cmd":"safety", "enabled": true}
            cmd = payload.get("cmd")

            if cmd == "set_mode":
                mode_str = payload.get("mode")
                if mode_str == "NORMAL":
                    self.mode = OperationMode.NORMAL
                elif mode_str == "SAFETY":
                    self.mode = OperationMode.SAFETY
                elif mode_str == "ID_ASSIGNMENT":
                    self.mode = OperationMode.ID_ASSIGNMENT
                elif mode_str == "DEGRADED":
                    self.mode = OperationMode.DEGRADED
                return

            if cmd == "safety":
                enabled = payload.get("enabled")
                if isinstance(enabled, bool):
                    self.mode = OperationMode.SAFETY if enabled else OperationMode.NORMAL
                return

            # Extend here with other control commands
            return
    
    def can_handle(self, msg: can.Message) -> None:
        """
        This method handles one CAN message: decode and forward to MQTT status.
        """
        if self.mqtt is None:
            return
        if not self.mqtt.is_connected():
            # In DEGRADED mode, or broker down: drop status for now
            return

        try:
            decoded = protocol.decode(msg)
        except Exception:
            # Bad/unknown frame: ignore for now (or log later)
            return

        # Publish a compact status message
        # (You can later make topic-per-seat; for now keep it single status topic)
        payload: Dict[str, Any] = {
            "section": self.section_id,
            "mode": self.mode.name,
            "seat": decoded.get("seat"),
            "type": decoded.get("type"),
        }

        # Add known decoded fields if present
        if "occupied" in decoded:
            payload["occupied"] = decoded["occupied"]
        if "uptime_s" in decoded:
            payload["uptime_s"] = decoded["uptime_s"]

    def run(self) -> None:
        """
        Run the bridge loop: consume MQTT and CAN queues and dispatch.
        """
        if self.mqtt is None or self.can is None:
            raise RuntimeError("Bridge.start() must be called before Bridge.run().")

        # Simple periodic heartbeat publishing (optional)
        last_heartbeat = time.time()

        try:
            while self._running:
                # Process a few MQTT events quickly
                event = self.mqtt.get_rx(timeout=0.05)
                if event is not None:
                    self.mqtt_handle(event)

                # Process a few CAN frames quickly
                can_msg = self.can.get_rx(timeout=0.05)
                if can_msg is not None:
                    self.can_handle(can_msg)

                # Optional heartbeat/status every 1s
                now = time.time()
                if self.mqtt.is_connected() and (now - last_heartbeat) >= 1.0:
                    self.mqtt.publish_json(
                        self.status_topic,
                        {"section": self.section_id, "mode": self.mode.name, "alive": True},
                        qos=0,
                        retain=False,
                    )
                    last_heartbeat = now

        except KeyboardInterrupt:
            pass
        finally:
            self.stop()

    