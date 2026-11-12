"""
Tests for starting a run from the web app. The autouse launcher fixture replaces the real process,
and run_lock gives each test its own lock file, which a test holds to play "another run in progress".
"""
import fcntl
import sys

import pytest
from fastapi.testclient import TestClient

from src import runs
from src.api import main


@pytest.fixture
def client():
    return TestClient(main.app)


@pytest.fixture
def other_run(run_lock):
    """Holds the lock the way a run started by the timer or a terminal would."""
    with open(run_lock, "w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        yield


def test_nothing_is_running_at_first(client):
    assert client.get("/api/runs/latest").json() == {"running": False, "exit_code": None, "log": None}


def test_run_now_starts_one_run_in_the_background(client, launcher):
    response = client.post("/api/runs")

    assert response.status_code == 202
    assert response.json()["running"] is True
    assert len(launcher.processes) == 1


def test_a_second_click_is_refused_while_running(client, launcher):
    client.post("/api/runs")

    response = client.post("/api/runs")

    assert response.status_code == 409
    assert len(launcher.processes) == 1


def test_a_run_started_elsewhere_blocks_run_now(client, launcher, other_run):
    assert client.get("/api/runs/latest").json()["running"] is True

    assert client.post("/api/runs").status_code == 409
    assert launcher.processes == []


def test_checking_the_lock_does_not_keep_it(run_lock):
    assert runs.lock_is_held() is False
    # If checking left the lock taken, a real run would now skip itself.
    with open(run_lock, "w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)


def test_status_shows_the_log_and_how_the_run_ended(client, launcher):
    client.post("/api/runs")
    launcher.processes[0].exit_code = 0

    status = client.get("/api/runs/latest").json()

    assert status == {"running": False, "exit_code": 0, "log": "Scraping Inria...\n"}


def test_a_new_run_can_start_after_the_last_one_ended(client, launcher):
    client.post("/api/runs")
    launcher.processes[0].exit_code = 1

    assert client.post("/api/runs").status_code == 202
    assert len(launcher.processes) == 2


def test_status_shows_only_the_end_of_a_long_log(client, run_lock, monkeypatch):
    from src import config
    with open(config.RUN_LOG_PATH, "w") as log:
        log.writelines(f"line {i}\n" for i in range(runs.LOG_LINES + 50))

    log = client.get("/api/runs/latest").json()["log"]

    assert log.splitlines()[0] == "line 50"
    assert len(log.splitlines()) == runs.LOG_LINES


def test_the_run_command_is_the_same_as_the_timer(monkeypatch):
    # The button and the timer must run the same thing, with this project's Python.
    assert runs.RUN_COMMAND == [sys.executable, "-u", "-m", "scheduler.run_daily"]
