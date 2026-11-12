"""The saved job history: what a run records, reading older rows, and clearing it."""
import sqlite3

import pytest

from src.agents.graph import compile_graph
from src.agents.state import initial_state
from src.db.seen_jobs import all_seen, backup_path, clear_seen, mark_seen, seen_keys
from src.evaluation.evaluate_scoring import export_labels

from conftest import make_job, make_match


@pytest.fixture
def db(monkeypatch, tmp_path):
    path = str(tmp_path / "seen.sqlite3")
    monkeypatch.setattr("src.config.SEEN_JOBS_DB", path)
    return path


def job(key="inria:1", title="Internship in NLP", score=78, **extra):
    return {
        "key": key,
        "title": title,
        "url": f"https://jobs.example/{key}",
        "score": score,
        "llm_score": score,
        "domain_fit": "adjacent",
        "contract_type": "internship",
        "rationale": "Good fit <with> *special* characters.",
        "matched_skills": ["Python"],
        "missing_skills": ["C++"],
        "letter": "Dear team,\n\nA letter.\n\nAbdelhak",
        "issues": [],
        **extra,
    }


def test_pipeline_saves_what_the_web_app_shows(world):
    world.jobs = [make_job("1", "Internship strong"), make_job("2", "Internship capped")]
    world.scores = {
        "strong": make_match(78, domain_fit="adjacent"),
        "capped": make_match(78, domain_fit="none"),
    }
    world.unsupported = {"truthful": ["never located"]}
    world.revised_letter = "Dear team,\n\nStill a truthful letter.\n\nAbdelhak"

    compile_graph().invoke(initial_state())

    saved = {row["title"]: row for row in all_seen()}
    strong, capped = saved["Internship strong"], saved["Internship capped"]

    assert strong["letter"] == world.revised_letter
    assert strong["issues"][0]["quote"] == "never located"
    assert strong["domain_fit"] == "adjacent"
    assert strong["rationale"] == "Good overlap."
    assert strong["matched_skills"] == ["Python"]
    assert strong["contract_type"] == "internship"
    assert capped["score"] == 60
    assert capped["llm_score"] == 78
    assert capped["letter"] is None


@pytest.mark.parametrize("is_internship, expected", [(1, "internship"), (0, "other"), (None, None)])
def test_rows_saved_before_contract_types_are_read_through_is_internship(db, is_internship, expected):
    mark_seen([job()])
    conn = sqlite3.connect(db)
    conn.execute("UPDATE seen_jobs SET contract_type = NULL, is_internship = ?", (is_internship,))
    conn.commit()
    conn.close()

    row = all_seen()[0]
    assert row["contract_type"] == expected
    assert "is_internship" not in row


def test_results_dont_affect_dedup_or_evaluation_export(db, tmp_path):
    mark_seen([job()])
    path = tmp_path / "labels.csv"
    assert export_labels(str(path)) == 1
    assert path.read_text(encoding="utf-8").splitlines()[0] == "key,title,url,score,label"


def test_clearing_an_empty_history_keeps_the_previous_backup(db):
    mark_seen([job()])
    assert clear_seen() == 1
    assert clear_seen() == 0
    assert len(all_seen(backup_path(db))) == 1
