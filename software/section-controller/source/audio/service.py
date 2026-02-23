from __future__ import annotations

import dataclasses
import logging
import os
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Optional

from .config import AudioConfig
from .types import AudioState, AudioStatus

LOGGER = logging.getLogger(__name__)
_UNSET = object()


class AudioService:
    def __init__(self, config: AudioConfig, logger: logging.Logger | None = None) -> None:
        self._config = config
        self._logger = logger or LOGGER
        self._lock = threading.Lock()
        self._stop_event = threading.Event()
        self._monitor_thread: Optional[threading.Thread] = None
        self._proc: Optional[subprocess.Popen[bytes]] = None
        self._started = False
        self._stopping = False
        self._backoff_s = 0.5
        self._status = AudioStatus(
            state=AudioState.STOPPED,
            pid=None,
            restart_count=0,
            last_error=None,
            last_transition_ts=time.monotonic(),
            backoff_s=None,
        )

        self._source_root = Path(__file__).resolve().parent.parent
        self._runner_module_cmd = [sys.executable, "-m", "audio.runner"]

    def start(self) -> None:
        with self._lock:
            if self._started:
                return
            self._started = True
            self._stopping = False
            self._stop_event.clear()
            self._backoff_s = 0.5
            self._set_status_locked(
                state=AudioState.STARTING,
                pid=None,
                last_error=None,
                backoff_s=None,
            )

        self._spawn_runner()
        self._ensure_monitor_thread()

    def stop(self) -> None:
        with self._lock:
            if not self._started and self._proc is None:
                self._set_status_locked(
                    state=AudioState.STOPPED,
                    pid=None,
                    backoff_s=None,
                )
                return
            self._started = False
            self._stopping = True
            self._stop_event.set()
            proc = self._proc

        self._stop_process(proc)

        monitor = None
        with self._lock:
            monitor = self._monitor_thread
        if monitor is not None and monitor.is_alive() and monitor is not threading.current_thread():
            monitor.join(timeout=2.5)

        with self._lock:
            self._monitor_thread = None
            self._proc = None
            self._set_status_locked(
                state=AudioState.STOPPED,
                pid=None,
                backoff_s=None,
            )

    def status(self) -> AudioStatus:
        with self._lock:
            return dataclasses.replace(self._status)

    def _ensure_monitor_thread(self) -> None:
        with self._lock:
            if self._monitor_thread is not None and self._monitor_thread.is_alive():
                return
            self._monitor_thread = threading.Thread(
                target=self._monitor_loop,
                name="AudioServiceMonitor",
                daemon=True,
            )
            thread = self._monitor_thread
        thread.start()

    def _build_runner_command(self) -> tuple[list[str], Path]:
        command = [
            *self._runner_module_cmd,
            "--mode",
            "stream",
            "--log-level",
            self._config.log_level,
        ]
        return command, self._source_root

    def _build_runner_env(self, cwd: Path) -> dict[str, str]:
        env = os.environ.copy()
        existing_pythonpath = env.get("PYTHONPATH", "")
        cwd_str = str(cwd)
        # Keep imports stable for `python -m audio.runner` whether main is launched
        # from repo root (`python source/main.py`) or from `source/` (`python main.py`).
        if existing_pythonpath:
            env["PYTHONPATH"] = os.pathsep.join([cwd_str, existing_pythonpath])
        else:
            env["PYTHONPATH"] = cwd_str
        return env

    def _spawn_runner(self) -> None:
        with self._lock:
            if not self._started:
                return
            self._set_status_locked(state=AudioState.STARTING, pid=None)

        command, cwd = self._build_runner_command()
        env = self._build_runner_env(cwd)
        self._logger.info("Starting audio runner process")
        try:
            proc = subprocess.Popen(command, cwd=str(cwd), env=env)
        except Exception as exc:
            with self._lock:
                self._status.last_error = f"spawn failed: {exc}"
                self._status.backoff_s = self._backoff_s
                self._status.last_transition_ts = time.monotonic()
                self._status.state = AudioState.ERROR
                self._status.restart_count += 1
            self._logger.exception("Failed to start audio runner")
            return

        with self._lock:
            self._proc = proc
            self._set_status_locked(
                state=AudioState.RUNNING_STREAM,
                pid=proc.pid,
                backoff_s=None,
            )

    def _stop_process(self, proc: Optional[subprocess.Popen[bytes]]) -> None:
        if proc is None:
            return

        if proc.poll() is not None:
            return

        self._logger.info("Stopping audio runner process pid=%s", proc.pid)
        try:
            proc.terminate()
            proc.wait(timeout=2.0)
        except subprocess.TimeoutExpired:
            self._logger.warning("Audio runner did not exit after SIGTERM/terminate; killing pid=%s", proc.pid)
            proc.kill()
            try:
                proc.wait(timeout=1.0)
            except subprocess.TimeoutExpired:
                self._logger.error("Audio runner still alive after kill attempt pid=%s", proc.pid)
        except Exception:
            self._logger.exception("Error while stopping audio runner pid=%s", proc.pid)

    def _monitor_loop(self) -> None:
        error_threshold = 10
        while not self._stop_event.is_set():
            with self._lock:
                started = self._started
                proc = self._proc
                stopping = self._stopping
            if not started:
                break
            if stopping:
                break
            if proc is None:
                with self._lock:
                    if not self._started or self._stopping:
                        break
                    backoff = self._backoff_s
                    self._status.backoff_s = backoff
                    self._status.last_transition_ts = time.monotonic()

                self._logger.warning(
                    "Audio runner missing while service is started. Restarting in %.1fs",
                    backoff,
                )
                if self._wait_or_stop(backoff):
                    break

                self._spawn_runner()
                with self._lock:
                    self._backoff_s = min(self._backoff_s * 2.0, 10.0)
                continue

            exit_code = proc.poll()
            if exit_code is None:
                self._wait_or_stop(0.2)
                continue

            with self._lock:
                if proc is self._proc:
                    self._proc = None
                if not self._started or self._stopping:
                    break
                self._status.restart_count += 1
                self._status.last_error = f"audio runner exited unexpectedly with code {exit_code}"
                self._status.backoff_s = self._backoff_s
                self._status.last_transition_ts = time.monotonic()
                self._status.state = (
                    AudioState.ERROR if self._status.restart_count >= error_threshold else AudioState.DEGRADED
                )
                self._status.pid = None
                backoff = self._backoff_s

            self._logger.warning(
                "Audio runner exited unexpectedly (code=%s). Restarting in %.1fs",
                exit_code,
                backoff,
            )
            if self._wait_or_stop(backoff):
                break

            self._spawn_runner()
            with self._lock:
                self._backoff_s = min(self._backoff_s * 2.0, 10.0)

    def _wait_or_stop(self, seconds: float) -> bool:
        return self._stop_event.wait(seconds)

    def _set_status_locked(
        self,
        *,
        state: AudioState,
        pid: Optional[int],
        last_error: object = _UNSET,
        backoff_s: Optional[float] | None = None,
    ) -> None:
        self._status.state = state
        self._status.pid = pid
        if last_error is not _UNSET:
            self._status.last_error = last_error if isinstance(last_error, str) or last_error is None else str(last_error)
        self._status.backoff_s = backoff_s
        self._status.last_transition_ts = time.monotonic()
