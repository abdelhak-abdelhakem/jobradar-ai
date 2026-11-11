"""The systemd timer that runs the pipeline. systemctl is faked for every test, in conftest.py."""
import json
import os
import shutil
import subprocess
import sys

import pytest

from src import config, scheduling
from src.settings import load_settings, save_settings


def unit(name):
    with open(os.path.join(scheduling.UNIT_DIR, name), encoding="utf-8") as f:
        return f.read()


def installed():
    return sorted(os.listdir(scheduling.UNIT_DIR)) if os.path.isdir(scheduling.UNIT_DIR) else []


@pytest.mark.parametrize("schedule, day, time, expected", [
    ("daily", "Mon", "08:00", "*-*-* 08:00:00"),
    ("weekly", "Fri", "18:30", "Fri *-*-* 18:30:00"),
])
def test_on_calendar(schedule, day, time, expected):
    assert scheduling.on_calendar(schedule, day, time) == expected


@pytest.mark.skipif(shutil.which("systemd-analyze") is None, reason="needs systemd")
@pytest.mark.parametrize("schedule, day", [("daily", "Mon"), ("weekly", "Sun")])
def test_real_systemd_accepts_the_calendar(schedule, day):
    # systemd-analyze only parses the expression; it changes nothing on the computer.
    calendar = scheduling.on_calendar(schedule, day, "23:59")
    result = subprocess.run(["systemd-analyze", "calendar", calendar], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr


def test_daily_schedule_installs_and_starts_the_timer(systemd):
    message = scheduling.apply_schedule("daily", "Mon", "08:00")

    assert message == "The pipeline runs every day at 08:00."
    assert installed() == ["jobradar.service", "jobradar.timer"]
    timer = unit("jobradar.timer")
    assert "OnCalendar=*-*-* 08:00:00" in timer
    assert "Persistent=true" in timer       # a run missed while the computer was off happens later
    service = unit("jobradar.service")
    assert f"WorkingDirectory={config.BASE_DIR}" in service
    assert f"ExecStart={sys.executable} -m scheduler.run_daily" in service
    assert systemd.commands == [("daemon-reload",), ("enable", "--now", "jobradar.timer")]


def test_changing_the_schedule_rewrites_the_timer(systemd):
    scheduling.apply_schedule("daily", "Mon", "08:00")
    message = scheduling.apply_schedule("weekly", "Fri", "18:30")

    assert message == "The pipeline runs every Fri at 18:30."
    assert "OnCalendar=Fri *-*-* 18:30:00" in unit("jobradar.timer")


def test_off_stops_and_removes_the_timer(systemd):
    scheduling.apply_schedule("daily", "Mon", "08:00")
    systemd.commands.clear()

    assert scheduling.apply_schedule("off", "Mon", "08:00") == "The pipeline isn't scheduled."
    assert installed() == []
    assert systemd.commands == [("disable", "--now", "jobradar.timer"), ("daemon-reload",)]


def test_off_with_nothing_installed_disables_nothing(systemd):
    scheduling.apply_schedule("off", "Mon", "08:00")
    assert systemd.commands == [("daemon-reload",)]


@pytest.mark.parametrize("schedule, day, time", [
    ("hourly", "Mon", "08:00"), ("weekly", "Monday", "08:00"), ("daily", "Mon", "8:00"), ("daily", "Mon", "24:00"),
])
def test_invalid_schedule_changes_nothing(systemd, schedule, day, time):
    with pytest.raises(ValueError):
        scheduling.apply_schedule(schedule, day, time)
    assert installed() == []
    assert systemd.commands == []


def test_systemd_failure_is_reported(systemd):
    systemd.fail = True
    with pytest.raises(scheduling.ScheduleError):
        scheduling.apply_schedule("daily", "Mon", "08:00")


def test_next_run_is_none_without_an_active_timer():
    assert scheduling.next_run() is None


def test_next_run_comes_from_systemd(monkeypatch):
    answers = {"is-active": "active", "show": "Thu 2026-11-12 08:00:00 CET"}
    monkeypatch.setattr(scheduling, "systemctl", lambda *args: answers[args[0]])
    assert scheduling.next_run() == "Thu 2026-11-12 08:00:00 CET"


# Schedule settings

def test_schedule_is_off_by_default():
    settings = load_settings()
    assert (settings["schedule"], settings["schedule_day"], settings["schedule_time"]) == ("off", "Mon", "08:00")


@pytest.mark.parametrize("name, value", [
    ("schedule", "hourly"), ("schedule_day", "Monday"), ("schedule_time", "8:00"), ("schedule_time", "08:60"),
    ("schedule_time", 800),
])
def test_invalid_schedule_settings_fall_back_on_their_own(settings_file, name, value):
    with open(settings_file, "w", encoding="utf-8") as f:
        json.dump({"sources": ["cnrs"], name: value}, f)
    settings = load_settings()
    assert settings[name] == {"schedule": "off", "schedule_day": "Mon", "schedule_time": "08:00"}[name]
    assert settings["sources"] == ["cnrs"]


@pytest.mark.parametrize("arguments", [{"schedule": "hourly"}, {"schedule_day": "Monday"}, {"schedule_time": "25:00"}])
def test_invalid_schedule_settings_cannot_be_saved(settings_file, arguments):
    with pytest.raises(ValueError):
        save_settings(**arguments)
    assert not os.path.exists(settings_file)
