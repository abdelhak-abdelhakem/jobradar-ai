"""Records which jobs are finished, so later runs don't score or send them again."""
import os
import sqlite3
from contextlib import closing
from datetime import datetime, timezone
from typing import TypedDict

from src import config


class SeenJob(TypedDict):
    key: str
    title: str
    url: str
    score: int


def _connect(path: str | None) -> sqlite3.Connection:
    path = path or config.SEEN_JOBS_DB
    os.makedirs(os.path.dirname(path), exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute(
        """CREATE TABLE IF NOT EXISTS seen_jobs (
            key TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            url TEXT NOT NULL,
            score INTEGER NOT NULL,
            seen_at TEXT NOT NULL
        )"""
    )
    return conn


def seen_keys(path: str | None = None) -> set[str]:
    with closing(_connect(path)) as conn:
        return {row["key"] for row in conn.execute("SELECT key FROM seen_jobs")}


def mark_seen(jobs: list[SeenJob], path: str | None = None) -> None:
    now = datetime.now(timezone.utc).isoformat()
    with closing(_connect(path)) as conn, conn:
        conn.executemany(
            "INSERT OR REPLACE INTO seen_jobs (key, title, url, score, seen_at) VALUES (?, ?, ?, ?, ?)",
            [(j["key"], j["title"], j["url"], j["score"], now) for j in jobs],
        )


def all_seen(path: str | None = None) -> list[dict]:
    with closing(_connect(path)) as conn:
        rows = conn.execute("SELECT key, title, url, score FROM seen_jobs ORDER BY score DESC")
        return [dict(row) for row in rows]
