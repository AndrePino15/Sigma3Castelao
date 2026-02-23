from __future__ import annotations

import argparse
import logging
import signal
import shutil
import subprocess
import threading
import time

from .config import AudioConfig
from .gst_pipeline import build_fallback_cmd, build_stream_cmd

LOGGER = logging.getLogger(__name__)
STABILITY_S = 1.0
RETRY_BACKOFF_MIN_S = 0.5
RETRY_BACKOFF_MAX_S = 5.0


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Audio worker process (Phase 3 stream/fallback runner)")
    parser.add_argument("--log-level", default="INFO")
    parser.add_argument("--mode", choices=["fallback", "stream"], default="fallback")
    parser.add_argument("--dry-run", action="store_true", help="Print command(s) and exit")
    return parser


def _terminate(proc: subprocess.Popen | None) -> None:
    if proc is None or proc.poll() is not None:
        return
    proc.terminate()
    try:
        proc.wait(timeout=2.0)
    except subprocess.TimeoutExpired:
        proc.kill()
        try:
            proc.wait(timeout=1.0)
        except subprocess.TimeoutExpired:
            LOGGER.warning("gst pipeline still alive after kill")


def _spawn_pipeline(cmd: list[str], label: str) -> subprocess.Popen:
    LOGGER.info("Starting %s pipeline: %s", label, " ".join(cmd))
    return subprocess.Popen(cmd)


def _wait_for_exit_or_stop(proc: subprocess.Popen, stop_event: threading.Event, poll_s: float = 0.2) -> int | None:
    while not stop_event.is_set():
        exit_code = proc.poll()
        if exit_code is not None:
            return exit_code
        stop_event.wait(poll_s)
    return None


def _wait_for_stability_or_exit(
    proc: subprocess.Popen,
    stop_event: threading.Event,
    stability_s: float,
    poll_s: float = 0.1,
) -> tuple[bool, int | None]:
    deadline = time.monotonic() + stability_s
    while not stop_event.is_set():
        exit_code = proc.poll()
        if exit_code is not None:
            return False, exit_code
        now = time.monotonic()
        if now >= deadline:
            return True, None
        stop_event.wait(min(poll_s, max(0.0, deadline - now)))
    return False, None


def _wait_until_retry(
    fallback_proc: subprocess.Popen | None,
    stop_event: threading.Event,
    delay_s: float,
) -> tuple[bool, subprocess.Popen | None]:
    deadline = time.monotonic() + delay_s
    proc = fallback_proc

    while not stop_event.is_set():
        if proc is not None:
            exit_code = proc.poll()
            if exit_code is not None:
                LOGGER.warning("Fallback pipeline exited with code %s; restarting fallback", exit_code)
                proc = None

        if proc is None and not stop_event.is_set():
            return False, None

        now = time.monotonic()
        if now >= deadline:
            return False, proc
        stop_event.wait(min(0.2, max(0.0, deadline - now)))

    return True, proc


def _run_fallback_only(
    cmd: list[str],
    stop_event: threading.Event,
    active_procs: list[subprocess.Popen | None],
) -> int:
    fallback_proc: subprocess.Popen | None = None
    try:
        fallback_proc = _spawn_pipeline(cmd, "fallback")
        active_procs[1] = fallback_proc
    except FileNotFoundError as exc:
        LOGGER.error("failed to launch gst pipeline: %s", exc)
        return 2
    except Exception as exc:
        LOGGER.error("gst pipeline failed to start: %s", exc)
        return 2

    try:
        exit_code = _wait_for_exit_or_stop(fallback_proc, stop_event)
        if stop_event.is_set():
            return 0
        final_code = fallback_proc.wait() if exit_code is None else exit_code
        LOGGER.info("fallback pipeline exited with code %s", final_code)
        return final_code
    finally:
        _terminate(fallback_proc)
        active_procs[1] = None


def _run_auto_mode(
    stream_cmd: list[str],
    fallback_cmd: list[str],
    stop_event: threading.Event,
    active_procs: list[subprocess.Popen | None],
) -> int:
    stream_proc: subprocess.Popen | None = None
    fallback_proc: subprocess.Popen | None = None
    retry_backoff_s = RETRY_BACKOFF_MIN_S

    try:
        while not stop_event.is_set():
            try:
                stream_proc = _spawn_pipeline(stream_cmd, "stream")
                active_procs[0] = stream_proc
            except FileNotFoundError as exc:
                LOGGER.error("failed to launch stream pipeline: %s", exc)
                return 2
            except Exception as exc:
                LOGGER.warning("stream pipeline failed to start; switching to fallback: %s", exc)
                stream_proc = None
                active_procs[0] = None
            else:
                LOGGER.info("State transition: FALLBACK->STREAM (or startup->STREAM)")
                exit_code = _wait_for_exit_or_stop(stream_proc, stop_event)
                if stop_event.is_set():
                    return 0
                stream_exit = stream_proc.wait() if exit_code is None else exit_code
                LOGGER.info("Stream pipeline exited with code %s", stream_exit)
                _terminate(stream_proc)
                stream_proc = None
                active_procs[0] = None
                LOGGER.info("State transition: STREAM->FALLBACK")

            if stop_event.is_set():
                return 0

            if fallback_proc is None:
                try:
                    fallback_proc = _spawn_pipeline(fallback_cmd, "fallback")
                    active_procs[1] = fallback_proc
                except FileNotFoundError as exc:
                    LOGGER.error("failed to launch fallback pipeline: %s", exc)
                    return 2
                except Exception as exc:
                    LOGGER.error("fallback pipeline failed to start: %s", exc)
                    return 2

            while not stop_event.is_set():
                LOGGER.info("Stream retry scheduled in %.1fs while fallback is active", retry_backoff_s)
                stop_now, fallback_proc = _wait_until_retry(fallback_proc, stop_event, retry_backoff_s)
                if stop_now:
                    return 0

                if fallback_proc is None:
                    active_procs[1] = None
                    try:
                        fallback_proc = _spawn_pipeline(fallback_cmd, "fallback")
                        active_procs[1] = fallback_proc
                    except FileNotFoundError as exc:
                        LOGGER.error("failed to relaunch fallback pipeline: %s", exc)
                        return 2
                    except Exception as exc:
                        LOGGER.error("fallback pipeline relaunch failed: %s", exc)
                        return 2
                    continue

                LOGGER.info("Attempting stream recovery probe (backoff=%.1fs)", retry_backoff_s)
                probe_proc: subprocess.Popen | None = None
                try:
                    probe_proc = _spawn_pipeline(stream_cmd, "stream-probe")
                    active_procs[0] = probe_proc
                except FileNotFoundError as exc:
                    LOGGER.error("failed to launch stream probe: %s", exc)
                    return 2
                except Exception as exc:
                    LOGGER.warning("stream probe failed to start: %s", exc)
                    active_procs[0] = None
                    retry_backoff_s = min(retry_backoff_s * 2.0, RETRY_BACKOFF_MAX_S)
                    continue

                stable, probe_exit = _wait_for_stability_or_exit(probe_proc, stop_event, STABILITY_S)
                if stop_event.is_set():
                    _terminate(probe_proc)
                    active_procs[0] = None
                    return 0

                if not stable:
                    code = probe_proc.wait() if probe_exit is None else probe_exit
                    LOGGER.info(
                        "Stream probe exited before stability window (code=%s); staying on fallback",
                        code,
                    )
                    _terminate(probe_proc)
                    active_procs[0] = None
                    retry_backoff_s = min(retry_backoff_s * 2.0, RETRY_BACKOFF_MAX_S)
                    continue

                LOGGER.info("State transition: FALLBACK->STREAM (probe stable for %.1fs)", STABILITY_S)
                _terminate(fallback_proc)
                fallback_proc = None
                active_procs[1] = None
                stream_proc = probe_proc
                probe_proc = None
                active_procs[0] = stream_proc
                retry_backoff_s = RETRY_BACKOFF_MIN_S

                exit_code = _wait_for_exit_or_stop(stream_proc, stop_event)
                if stop_event.is_set():
                    return 0
                stream_exit = stream_proc.wait() if exit_code is None else exit_code
                LOGGER.info("Stream pipeline exited with code %s", stream_exit)
                _terminate(stream_proc)
                stream_proc = None
                active_procs[0] = None
                LOGGER.info("State transition: STREAM->FALLBACK")

                try:
                    fallback_proc = _spawn_pipeline(fallback_cmd, "fallback")
                    active_procs[1] = fallback_proc
                except FileNotFoundError as exc:
                    LOGGER.error("failed to relaunch fallback pipeline after stream loss: %s", exc)
                    return 2
                except Exception as exc:
                    LOGGER.error("fallback pipeline relaunch failed after stream loss: %s", exc)
                    return 2
                break

        return 0
    finally:
        _terminate(stream_proc)
        _terminate(fallback_proc)
        active_procs[0] = None
        active_procs[1] = None


def main() -> int:
    args = _build_parser().parse_args()

    logging.basicConfig(
        level=getattr(logging, str(args.log_level).upper(), logging.INFO),
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    )

    config = AudioConfig.from_env()
    try:
        fallback_cmd = build_fallback_cmd(config)
        stream_cmd = build_stream_cmd(config) if args.mode == "stream" else None
    except ValueError as exc:
        LOGGER.error("failed to build pipeline command: %s", exc)
        return 2

    if args.dry_run:
        if args.mode == "fallback":
            print(fallback_cmd)
        else:
            print(stream_cmd)
            print(fallback_cmd)
        return 0

    gst_path = shutil.which("gst-launch-1.0")
    if not gst_path:
        LOGGER.error("gst-launch-1.0 not found in PATH")
        return 2

    fallback_cmd[0] = gst_path
    if stream_cmd is not None:
        stream_cmd[0] = gst_path

    stop_event = threading.Event()
    active_procs: list[subprocess.Popen | None] = [None, None]

    def _handle_shutdown(signum: int, _frame: object) -> None:
        LOGGER.info("received signal %s, shutting down audio worker", signum)
        stop_event.set()
        _terminate(active_procs[0])
        _terminate(active_procs[1])

    signal.signal(signal.SIGINT, _handle_shutdown)
    if hasattr(signal, "SIGTERM"):
        signal.signal(signal.SIGTERM, _handle_shutdown)

    try:
        if args.mode == "fallback":
            return _run_fallback_only(fallback_cmd, stop_event, active_procs)

        # Auto mode: prefer stream, fall back to silence, and keep retrying stream.
        return _run_auto_mode(stream_cmd or [], fallback_cmd, stop_event, active_procs)
    finally:
        for proc in active_procs:
            _terminate(proc)


if __name__ == "__main__":
    raise SystemExit(main())
