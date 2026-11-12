"""
Tests for the web API. TestClient sends real HTTP requests to the app without starting a server.
The autouse fixtures in conftest.py give every test its own settings file, job history, and fake systemd.
"""
import json

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src import config
from src.api import main
from src.db.seen_jobs import all_seen, mark_seen
from src.settings import DEFAULT_SETTINGS, load_settings


@pytest.fixture
def client():
    return TestClient(main.app)


def saved_job(key="inria:1", score=80, **fields) -> dict:
    return {"key": key, "title": f"Job {key}", "url": f"https://jobs.example/{key}", "score": score, **fields}


# Options

def test_options_list_every_choice(client):
    options = client.get("/api/options").json()

    assert [c["name"] for c in options["contracts"]] == list(config.CONTRACTS)
    assert [s["name"] for s in options["sources"]] == ["inria", "cnrs", "cea"]
    assert options["max_top_k"] == config.MAX_TOP_K
    assert options["match_threshold"] == config.MATCH_SCORE_THRESHOLD


def test_options_name_the_boards_a_contract_skips(client):
    contracts = {c["name"]: c for c in client.get("/api/options").json()["contracts"]}

    assert contracts["internship"]["skipped_sources"] == []
    assert contracts["phd"]["skipped_sources"] == ["cea"]


# Settings

def test_get_settings_returns_the_defaults_when_nothing_is_saved(client):
    settings = client.get("/api/settings").json()

    for name, value in DEFAULT_SETTINGS.items():
        assert settings[name] == value
    assert settings["next_run"] is None


def test_patch_saves_only_the_fields_given(client):
    response = client.patch("/api/settings", json={"contract_type": "phd", "top_k": 3})

    assert response.status_code == 200
    assert response.json()["contract_type"] == "phd"
    saved = load_settings()
    assert (saved["contract_type"], saved["top_k"]) == ("phd", 3)
    assert saved["sources"] == DEFAULT_SETTINGS["sources"]


def test_patch_with_an_invalid_value_saves_nothing(client, settings_file):
    response = client.patch("/api/settings", json={"top_k": 3, "sources": []})

    assert response.status_code == 422
    assert response.json()["detail"] == "Select at least one source."
    assert load_settings()["top_k"] == DEFAULT_SETTINGS["top_k"]


def test_patch_rejects_an_unknown_field(client):
    # A misspelled field would otherwise be dropped, and the user would think it was saved.
    response = client.patch("/api/settings", json={"top_kk": 3})

    assert response.status_code == 422


def test_patch_cannot_change_the_schedule(client):
    # The schedule must go through /api/schedule, which installs the timer, or the two would disagree.
    response = client.patch("/api/settings", json={"schedule": "daily"})

    assert response.status_code == 422
    assert load_settings()["schedule"] == "off"


@pytest.mark.parametrize("credentials, missing", [
    (("token", "42", "bot@gmail.com", "pw"), []),
    ((None, "42", "bot@gmail.com", "pw"), ["telegram"]),
    (("token", "42", "bot@gmail.com", ""), ["gmail"]),
])
def test_settings_report_missing_credentials(client, monkeypatch, credentials, missing):
    for name, value in zip(("TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID", "GMAIL_ADDRESS", "GMAIL_APP_PASSWORD"),
                           credentials):
        monkeypatch.setattr(config, name, value)

    assert client.get("/api/settings").json()["missing_credentials"] == missing


# Schedule

def test_schedule_installs_the_timer_then_saves(client, systemd):
    response = client.put("/api/schedule", json={"schedule": "weekly", "day": "Fri", "time": "07:30"})

    assert response.status_code == 200
    assert response.json()["message"] == "The pipeline runs every Fri at 07:30."
    assert ("enable", "--now", "jobradar.timer") in systemd.commands
    saved = load_settings()
    assert (saved["schedule"], saved["schedule_day"], saved["schedule_time"]) == ("weekly", "Fri", "07:30")


def test_schedule_is_not_saved_when_systemd_fails(client, systemd):
    systemd.fail = True

    response = client.put("/api/schedule", json={"schedule": "daily", "day": "Mon", "time": "08:00"})

    assert response.status_code == 502
    assert load_settings()["schedule"] == "off"


@pytest.mark.parametrize("body", [
    {"schedule": "hourly", "day": "Mon", "time": "08:00"},
    {"schedule": "daily", "day": "Monday", "time": "08:00"},
    {"schedule": "daily", "day": "Mon", "time": "8am"},
])
def test_invalid_schedule_touches_nothing(client, systemd, body):
    response = client.put("/api/schedule", json=body)

    assert response.status_code == 422
    assert systemd.commands == []
    assert load_settings()["schedule"] == "off"


# Jobs and history

def test_jobs_are_empty_before_any_run(client):
    assert client.get("/api/jobs").json() == []


def test_jobs_come_best_first_with_their_source(client):
    mark_seen([saved_job("cnrs:7", 50, llm_score=60), saved_job("inria:1", 90, llm_score=90, letter="Dear team")])

    jobs = client.get("/api/jobs").json()

    assert [job["key"] for job in jobs] == ["inria:1", "cnrs:7"]
    assert [job["source"] for job in jobs] == ["inria", "cnrs"]
    assert jobs[0]["letter"] == "Dear team"


def test_old_rows_without_an_llm_score_fall_back_to_the_final_score(client):
    mark_seen([saved_job(score=75)])

    assert client.get("/api/jobs").json()[0]["llm_score"] == 75


def test_jobs_response_is_plain_json(client):
    mark_seen([saved_job(matched_skills=["Python"], issues=[{"quote": "x", "reason": "y"}])])

    job = client.get("/api/jobs").json()[0]

    # Lists are decoded, not sent as the JSON strings stored in SQLite.
    assert job["matched_skills"] == ["Python"]
    assert job["issues"] == [{"quote": "x", "reason": "y"}]
    json.dumps(job)


def test_delete_history_clears_and_backs_up(client):
    mark_seen([saved_job("inria:1"), saved_job("inria:2")])

    response = client.delete("/api/history").json()

    assert response == {"deleted": 2, "backup": "seen.backup.sqlite3"}
    assert all_seen() == []


def test_delete_empty_history_reports_no_backup(client):
    assert client.delete("/api/history").json() == {"deleted": 0, "backup": None}


def test_other_websites_cannot_call_the_api(client):
    # No CORS headers: the browser blocks a page on another site from reading or sending JSON requests.
    response = client.options("/api/history", headers={
        "Origin": "https://evil.example",
        "Access-Control-Request-Method": "DELETE",
    })

    assert "access-control-allow-origin" not in response.headers


# Serving the built web app

def test_the_built_web_app_is_served_next_to_the_api(tmp_path):
    (tmp_path / "index.html").write_text("<h1>JobRadar</h1>")
    app = FastAPI()

    @app.get("/api/ping")
    def ping():
        return {"ok": True}

    main.serve_frontend(app, str(tmp_path))
    client = TestClient(app)

    assert client.get("/").text == "<h1>JobRadar</h1>"
    assert client.get("/api/ping").json() == {"ok": True}   # the API routes still win


def test_without_a_build_only_the_api_is_served(tmp_path):
    app = FastAPI()
    main.serve_frontend(app, str(tmp_path / "missing"))

    assert TestClient(app).get("/").status_code == 404
