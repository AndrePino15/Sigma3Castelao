from __future__ import annotations
import threading
import queue
import logging
from typing import Optional, List, Dict, Any
import can

LOGGER = logging.getLogger(__name__)


class CanInterface:
    """
    Thin wrapper around python-can Bus for SocketCAN.
    This class keeps CAN plumbing separate from protocol/application logic.
    """

    def __init__(self, channel: str = "can0", interface: str = "socketcan", rx_maxsize: int = 0) -> None:
        # with rx_maxsize = 0 the queue can be infinite
        self.channel = channel
        self.interface = interface
        self.bus = can.interface.Bus(channel=channel, interface=interface)

        self.rx_queue: "queue.Queue[can.Message]" = queue.Queue(maxsize=rx_maxsize)

        self._rx_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._rx_failed = False
        self._rx_error: Optional[str] = None

    def set_filters(self, filters: List[Dict[str, Any]]) -> None:
        """ Example filter dict: {"can_id": 0x200, "can_mask": 0x700, "extended": False} """
        self.bus.set_filters(filters)

    def send(self, msg: can.Message) -> None:
        """Transmit one CAN frame via python-can."""
        self.bus.send(msg)

    def recv(self, timeout: float = 1.0) -> Optional[can.Message]:
        return self.bus.recv(timeout)

    def start_rx(self, timeout: float = 1.0) -> None:
        """
        Start a background RX loop that blocks on recv() and enqueues messages.
        Keep this loop extremely lightweight to avoid dropping frames under load.
        """
        if self._rx_thread and self._rx_thread.is_alive():
            return

        self._stop_event.clear()
        self.clear_rx_failure()

        def _loop() -> None:
            while not self._stop_event.is_set():
                try:
                    msg = self.bus.recv(timeout)
                except Exception as exc:
                    self._rx_failed = True
                    self._rx_error = f"{type(exc).__name__}: {exc}"
                    LOGGER.error(
                        "CAN RX loop failed on %s/%s: %s",
                        self.channel,
                        self.interface,
                        self._rx_error,
                    )
                    self._stop_event.set()
                    break
                if msg is None:
                    continue
                try:
                    # Non-blocking put prevents deadlock if queue is full.
                    self.rx_queue.put_nowait(msg)
                except queue.Full:
                    # Decide policy: drop newest, drop oldest, or block.
                    # For now: drop the message (and later add logging/counter).
                    pass

        self._rx_thread = threading.Thread(target=_loop, name="can-rx", daemon=True)
        self._rx_thread.start()

    def get_rx(self, timeout: Optional[float] = None) -> Optional[can.Message]:
        """
        Blocking read from the RX queue. Returns None on timeout.
        """
        try:
            return self.rx_queue.get(timeout=timeout)
        except queue.Empty:
            return None

    def has_rx_failure(self) -> bool:
        """Return whether the RX thread stopped due to a receive exception."""
        return self._rx_failed

    def rx_error_summary(self) -> Optional[str]:
        """Return a short string describing the last RX thread failure."""
        return self._rx_error

    def clear_rx_failure(self) -> None:
        """Reset RX thread failure markers before starting a new RX loop."""
        self._rx_failed = False
        self._rx_error = None

    def close(self) -> None:
        self._stop_event.set()
        if self._rx_thread:
            self._rx_thread.join(timeout=2.0)
        self.bus.shutdown()
