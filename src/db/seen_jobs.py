"""Records finished jobs and their results, so later runs skip them and the dashboard can show them."""
import json
import os
import sqlite3
from contextlib import closing
from datetime import datetime, timezone
from typing import NotRequired, TypedDict

from src import config

JSON_COLUMNS = ("matched_skills", "missing_skills", "issues")

# Added after the first version of this table. Older rows have NULL in these columns.
# is_internship is no longer written: contract_type replaced it, and old rows are read through it.
RESULT_COLUMNS = {
    "company": "TEXT",
    "llm_score": "INTEGER",
    "domain_fit": "TEXT",
    "is_internship": "INTEGER",
    "contract_type": "TEXT",
    "rationale": "TEXT",
    "matched_skills": "TEXT",
    "missing_skills": "TEXT",
    "letter": "TEXT",
    "issues": "TEXT",
}


class SeenJob(TypedDict):
    key: str
    title: str
    url: str
    score: int
    company: NotRequired[str | None]
    llm_score: NotRequired[int]
    domain_fit: NotRequired[str]
    contract_type: NotRequired[str]
    rationale: NotRequired[str]
    matched_skills: NotRequired[list[str]]
    missing_skills: NotRequired[list[str]]
    letter: NotRequired[str | None]
    issues: NotRequired[list[dict]]


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
    existing = {row["name"] for row in conn.execute("PRAGMA table_info(seen_jobs)")}
    for column, column_type in RESULT_COLUMNS.items():
        if column not in existing:
            conn.execute(f"ALTER TABLE seen_jobs ADD COLUMN {column} {column_type}")
    return conn


def seen_keys(path: str | None = None) -> set[str]:
    with closing(_connect(path)) as conn:
        return {row["key"] for row in conn.execute("SELECT key FROM seen_jobs")}


def mark_seen(jobs: list[SeenJob], path: str | None = None) -> None:
    now = datetime.now(timezone.utc).isoformat()
    columns = ["key", "title", "url", "score", "seen_at", *RESULT_COLUMNS]
    placeholders = ", ".join("?" for _ in columns)

    def row(job: SeenJob) -> list:
        values = {**job, "seen_at": now}
        for column in JSON_COLUMNS:
            values[column] = json.dumps(job.get(column, []), ensure_ascii=False)
        return [values.get(column) for column in columns]

    with closing(_connect(path)) as conn, conn:
        conn.executemany(
            f"INSERT OR REPLACE INTO seen_jobs ({', '.join(columns)}) VALUES ({placeholders})",
            [row(job) for job in jobs],
        )


def all_seen(path: str | None = None) -> list[dict]:
    """Returns every finished job, highest score first. Fields older rows lack are None or empty."""
    with closing(_connect(path)) as conn:
        rows = conn.execute("SELECT * FROM seen_jobs ORDER BY score DESC, title").fetchall()

    jobs = []
    for row in rows:
        job = dict(row)
        for column in JSON_COLUMNS:
            job[column] = json.loads(job[column]) if job[column] else []
        # Rows saved before contract types only recorded whether the job was an internship.
        if job["contract_type"] is None and job["is_internship"] is not None:
            job["contract_type"] = "internship" if job["is_internship"] else "other"
        del job["is_internship"]
        jobs.append(job)
    return jobs
