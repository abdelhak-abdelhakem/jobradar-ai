"""
The web API the frontend talks to. It's a thin layer: each route calls the same functions the pipeline uses,
so the rules (which settings are valid, how the schedule is installed) live in one place.

  uvicorn src.api.main:app --reload

Once the web app is built (cd web && npm run build), this also serves it, so one command runs everything:
open http://127.0.0.1:8000. During frontend work, `npm run dev` serves it with live reload instead.

It has no login, so it must only listen on this computer (uvicorn's default, 127.0.0.1). It also has no CORS
setup on purpose: browsers then refuse JSON requests from other websites, so a page you visit can't change
your settings or clear your history through it.
"""
import os
from typing import Literal

from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict

from src import config
from src.agents.nodes.scrape import FILTERED_BY_CONTRACT
from src.db.seen_jobs import all_seen, backup_path, clear_seen
from src.runs import RunInProgress, run_status, start_run
from src.scheduling import ScheduleError, apply_schedule, next_run
from src.settings import CHANNELS, DELIVERY_MODES, SCHEDULES, SOURCES, WEEKDAYS, load_settings, save_settings

app = FastAPI(title="JobRadar API")


class SettingsUpdate(BaseModel):
    """The settings to change. A field left out keeps its saved value. save_settings() checks the values."""
    model_config = ConfigDict(extra="forbid")   # a misspelled field is an error, not silently ignored

    sources: list[str] | None = None
    channels: list[str] | None = None
    domain_keywords: list[str] | None = None
    contract_type: str | None = None
    delivery: str | None = None
    top_k: int | None = None


class ScheduleUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schedule: Literal[SCHEDULES]
    day: Literal[WEEKDAYS]
    time: str


def missing_credentials() -> list[str]:
    """Channels whose credentials aren't in .env, so they would send nothing."""
    needed = {
        "telegram": (config.TELEGRAM_BOT_TOKEN, config.TELEGRAM_CHAT_ID),
        "gmail": (config.GMAIL_ADDRESS, config.GMAIL_APP_PASSWORD),
    }
    return [name for name, values in needed.items() if not all(values)]


def settings_response(settings: dict) -> dict:
    """The saved settings, plus what the settings page shows next to them."""
    return {**settings, "missing_credentials": missing_credentials(), "next_run": next_run()}


@app.get("/api/options")
def get_options() -> dict:
    """Every choice the settings page offers, so the frontend never keeps its own copy of these lists."""
    return {
        "contracts": [
            {
                "name": name,
                "label": contract["label"],
                "skipped_sources": [s for s in FILTERED_BY_CONTRACT if s not in contract["site_codes"]],
            }
            for name, contract in config.CONTRACTS.items()
        ],
        "sources": [{"name": name, "label": label} for name, label in SOURCES.items()],
        "channels": [{"name": name, "label": label} for name, label in CHANNELS.items()],
        "delivery_modes": list(DELIVERY_MODES),
        "schedules": list(SCHEDULES),
        "weekdays": list(WEEKDAYS),
        "max_top_k": config.MAX_TOP_K,
        "match_threshold": config.MATCH_SCORE_THRESHOLD,
    }


@app.get("/api/settings")
def get_settings() -> dict:
    return settings_response(load_settings())


@app.patch("/api/settings")
def update_settings(update: SettingsUpdate) -> dict:
    try:
        settings = save_settings(**update.model_dump(exclude_none=True))
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    return settings_response(settings)


@app.put("/api/schedule")
def update_schedule(update: ScheduleUpdate) -> dict:
    # Apply first and save only if it worked, so the settings never show a schedule systemd doesn't have.
    try:
        message = apply_schedule(update.schedule, update.day, update.time)
    except ValueError:
        raise HTTPException(status_code=422, detail="The time must be in 24-hour HH:MM format, such as 08:00.")
    except ScheduleError as e:
        raise HTTPException(status_code=502, detail=str(e))
    settings = save_settings(schedule=update.schedule, schedule_day=update.day, schedule_time=update.time)
    return {**settings_response(settings), "message": message}


@app.get("/api/jobs")
def get_jobs() -> list[dict]:
    """Every finished job, highest score first."""
    jobs = all_seen()
    for job in jobs:
        job["source"] = job["key"].split(":", 1)[0]
        # Rows saved before the LLM score was recorded fall back to the final score.
        if job["llm_score"] is None:
            job["llm_score"] = job["score"]
    return jobs


@app.delete("/api/history")
def delete_history() -> dict:
    """Clears the finished jobs, so the next run scores them all again. The old ones are backed up first."""
    deleted = clear_seen()
    return {"deleted": deleted, "backup": os.path.basename(backup_path()) if deleted else None}


@app.post("/api/runs", status_code=202)
def post_run() -> dict:
    """Starts a pipeline run in the background. 202 means accepted: it has started, not finished."""
    try:
        start_run()
    except RunInProgress as e:
        raise HTTPException(status_code=409, detail=str(e))
    return run_status()


@app.get("/api/runs/latest")
def get_run() -> dict:
    return run_status()


WEB_DIST = os.path.join(config.BASE_DIR, "web", "dist")   # the built web app


def serve_frontend(app: FastAPI, dist: str) -> None:
    """Serves the built web app at /. Mounted last, so the /api routes above always win."""
    if os.path.isdir(dist):
        app.mount("/", StaticFiles(directory=dist, html=True), name="frontend")


serve_frontend(app, WEB_DIST)
