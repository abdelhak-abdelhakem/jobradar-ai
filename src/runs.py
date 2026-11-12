"""
Starts a pipeline run in the background and reports on it, for the web app's "Run now" button.

A run takes minutes, so it runs as a separate process: the API answers right away, and a crash in the
run can't take the API down. Whether a run is in progress comes from the lock scheduler/run_daily.py holds,
so a run started by the systemd timer counts too, and two runs can never overlap.
"""
import fcntl
import os
import subprocess
import sys

from src import config

RUN_COMMAND = [sys.executable, "-u", "-m", "scheduler.run_daily"]   # -u: print each line as it happens
LOG_LINES = 200   # how much of the log the web app shows

_process: subprocess.Popen | None = None   # the last run this API started, if any


class RunInProgress(Exception):
    pass


def launch(log) -> subprocess.Popen:
    """The single place a real process starts, so tests can replace it."""
    return subprocess.Popen(
        RUN_COMMAND,
        cwd=config.BASE_DIR,
        stdout=log,
        stderr=subprocess.STDOUT,
        start_new_session=True,   # keeps running if the API restarts
    )


def lock_is_held() -> bool:
    """True while some run holds the lock: one started here, by the timer, or in a terminal."""
    os.makedirs(os.path.dirname(config.RUN_LOCK_PATH), exist_ok=True)
    with open(config.RUN_LOCK_PATH, "a") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return True
        fcntl.flock(lock, fcntl.LOCK_UN)
        return False


def is_running() -> bool:
    # Our process counts too: just after it starts, it hasn't taken the lock yet.
    return lock_is_held() or (_process is not None and _process.poll() is None)


def start_run() -> None:
    """Starts a run whose output goes to config.RUN_LOG_PATH. Raises RunInProgress if one is running."""
    global _process
    if is_running():
        raise RunInProgress("A run is already in progress.")
    # Even if two clicks race past the check, the second run finds the lock taken and skips itself.
    with open(config.RUN_LOG_PATH, "w", encoding="utf-8") as log:
        _process = launch(log)


def run_status() -> dict:
    """Whether a run is in progress, how the last one started here ended, and the end of its log."""
    log = None
    if os.path.exists(config.RUN_LOG_PATH):
        with open(config.RUN_LOG_PATH, encoding="utf-8", errors="replace") as f:
            log = "".join(f.readlines()[-LOG_LINES:])
    return {
        "running": is_running(),
        # None while running, or when this API hasn't started a run (such as a timer run, or after a restart).
        "exit_code": _process.poll() if _process is not None else None,
        "log": log,
    }
