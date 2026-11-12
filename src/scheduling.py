"""
Runs the pipeline on a schedule with a systemd user timer, on Linux.

The web app can't do this itself: it only runs while its server is up. systemd always runs, so a
timer wakes up at the chosen time and starts jobradar.service, which runs scheduler/run_daily.py once.
With Persistent=true, a run missed while the computer was off happens as soon as it's back on.

  journalctl --user -u jobradar.service     # what the runs printed
  systemctl --user list-timers jobradar.timer   # when the next run is
"""
import os
import shutil
import subprocess
import sys

from src import config
from src.settings import SCHEDULES, WEEKDAYS, is_schedule_time

UNIT_NAME = "jobradar"
UNIT_DIR = os.path.expanduser("~/.config/systemd/user")   # user units: they run as you, without sudo


class ScheduleError(Exception):
    """systemd isn't available, or refused a command."""


def systemctl(*args: str) -> str:
    """The only place that runs systemctl, so tests can replace it. Returns what it printed."""
    if shutil.which("systemctl") is None:
        raise ScheduleError("systemd isn't available on this computer, so the pipeline can't be scheduled.")
    result = subprocess.run(["systemctl", "--user", *args], capture_output=True, text=True)
    if result.returncode != 0:
        raise ScheduleError(f"systemctl {' '.join(args)} failed: {result.stderr.strip()}")
    return result.stdout.strip()


def on_calendar(schedule: str, day: str, time: str) -> str:
    """The timer's OnCalendar value, such as "*-*-* 08:00:00" daily or "Mon *-*-* 08:00:00" weekly."""
    if schedule == "weekly":
        return f"{day} *-*-* {time}:00"
    return f"*-*-* {time}:00"


def service_text() -> str:
    # The Python that runs the web API has the project's packages, so the timer uses the same one.
    return f"""[Unit]
Description=JobRadar: find, score, and send new job offers

[Service]
Type=oneshot
WorkingDirectory={config.BASE_DIR}
ExecStart={sys.executable} -m scheduler.run_daily
Environment=PYTHONUNBUFFERED=1
"""


def timer_text(calendar: str) -> str:
    return f"""[Unit]
Description=Run JobRadar on a schedule

[Timer]
OnCalendar={calendar}
Persistent=true

[Install]
WantedBy=timers.target
"""


def describe(schedule: str, day: str, time: str) -> str:
    if schedule == "daily":
        return f"every day at {time}"
    if schedule == "weekly":
        return f"every {day} at {time}"
    return "off"


def apply_schedule(schedule: str, day: str, time: str) -> str:
    """
    Installs, updates, or removes the timer, and returns a sentence describing the schedule.
    Raises ValueError for an invalid schedule, and ScheduleError if systemd fails.
    """
    if schedule not in SCHEDULES or day not in WEEKDAYS or not is_schedule_time(time):
        raise ValueError("Invalid schedule.")

    service_path = os.path.join(UNIT_DIR, f"{UNIT_NAME}.service")
    timer_path = os.path.join(UNIT_DIR, f"{UNIT_NAME}.timer")

    if schedule == "off":
        if os.path.exists(timer_path):
            systemctl("disable", "--now", f"{UNIT_NAME}.timer")
        for path in (timer_path, service_path):
            if os.path.exists(path):
                os.remove(path)
        systemctl("daemon-reload")
        return "The pipeline isn't scheduled."

    os.makedirs(UNIT_DIR, exist_ok=True)
    with open(service_path, "w", encoding="utf-8") as f:
        f.write(service_text())
    with open(timer_path, "w", encoding="utf-8") as f:
        f.write(timer_text(on_calendar(schedule, day, time)))
    systemctl("daemon-reload")
    systemctl("enable", "--now", f"{UNIT_NAME}.timer")
    return f"The pipeline runs {describe(schedule, day, time)}."


def next_run() -> str | None:
    """When systemd will next run the pipeline, as it prints it, or None if no timer is active."""
    try:
        if systemctl("is-active", f"{UNIT_NAME}.timer") != "active":
            return None
        return systemctl("show", f"{UNIT_NAME}.timer", "--property=NextElapseUSecRealtime", "--value") or None
    except ScheduleError:
        return None
