import os
import sqlite3

import pytest
from streamlit.testing.v1 import AppTest

from src.agents.graph import compile_graph
from src.agents.state import initial_state
from src.db.seen_jobs import all_seen, mark_seen
from src.evaluation.evaluate_scoring import export_labels
from src.settings import load_settings

from conftest import make_job, make_match

APP = os.path.join(os.path.dirname(os.path.dirname(__file__)), "dashboard", "app.py")


@pytest.fixture
def db(monkeypatch, tmp_path):
    path = str(tmp_path / "seen.sqlite3")
    monkeypatch.setattr("src.config.SEEN_JOBS_DB", path)
    return path


def run_app():
    app = AppTest.from_file(APP, default_timeout=30).run()
    assert not app.exception
    return app


def job(key="inria:1", title="Internship in NLP", score=78, **extra):
    return {
        "key": key,
        "title": title,
        "url": f"https://jobs.example/{key}",
        "score": score,
        "llm_score": score,
        "domain_fit": "adjacent",
        "is_internship": True,
        "rationale": "Good fit <with> *special* characters.",
        "matched_skills": ["Python"],
        "missing_skills": ["C++"],
        "letter": "Dear team,\n\nA letter.\n\nAbdelhak",
        "issues": [],
        **extra,
    }


def metrics(app):
    return {metric.label: metric.value for metric in app.metric}


def test_empty_database_shows_how_to_start(db):
    app = run_app()
    assert "No results yet" in app.info[0].value
    assert not app.metric


def test_metrics_and_details(db):
    mark_seen([
        job("inria:1", "Strong flagged", 78, issues=[{"quote": "I know audio.", "reason": "Not in the CV."}]),
        job("inria:2", "Capped", 60, llm_score=78, domain_fit="none", letter=None),
        job("inria:3", "Weak", 40, letter=None),
    ])
    app = run_app()

    summary = metrics(app)
    assert summary["Jobs scored"] == "3"
    assert summary["Strong matches"] == "1"
    assert summary["Lowered by the caps"] == "1"
    assert summary["Letters to check"] == "1"

    assert app.subheader[0].value == "Strong flagged"
    assert "I know audio." in app.warning[0].value
    assert "A letter." in app.code[0].value


def test_selecting_a_job_without_a_letter(db):
    mark_seen([job("inria:1", "First", 78), job("inria:2", "Second", 60, llm_score=78, letter=None)])
    app = run_app()
    app.selectbox[0].select_index(1).run()
    assert not app.exception
    assert app.subheader[0].value == "Second"
    assert "below 70" in app.info[0].value
    assert not app.code


def test_rows_from_the_old_schema_still_load(db):
    conn = sqlite3.connect(db)
    conn.execute(
        "CREATE TABLE seen_jobs (key TEXT PRIMARY KEY, title TEXT NOT NULL, url TEXT NOT NULL,"
        " score INTEGER NOT NULL, seen_at TEXT NOT NULL)"
    )
    conn.execute("INSERT INTO seen_jobs VALUES ('inria:1', 'Old job', 'https://x/1', 78, '2026-10-31T16:00:00')")
    conn.commit()
    conn.close()

    app = run_app()

    assert metrics(app)["Jobs scored"] == "1"
    assert "older version" in app.warning[0].value
    assert app.subheader[0].value == "Old job"


def test_pipeline_saves_what_the_dashboard_needs(world):
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
    assert capped["score"] == 60
    assert capped["llm_score"] == 78
    assert capped["letter"] is None


def test_results_dont_affect_dedup_or_evaluation_export(db, tmp_path):
    mark_seen([job()])
    path = tmp_path / "labels.csv"
    assert export_labels(str(path)) == 1
    assert path.read_text(encoding="utf-8").splitlines()[0] == "key,title,url,score,label"


# Source settings in the sidebar

def test_sidebar_saves_the_chosen_sources(db):
    app = run_app()
    boxes = {box.label: box for box in app.sidebar.checkbox}
    assert all(box.value for box in boxes.values())   # all sources are on by default

    boxes["CNRS"].uncheck()
    app.sidebar.button[0].click().run()

    assert not app.exception
    assert "Saved" in app.sidebar.success[0].value
    assert load_settings()["sources"] == ["inria", "cea"]
    assert [box.value for box in run_app().sidebar.checkbox] == [True, False, True]


def test_sidebar_refuses_to_save_no_source(db, settings_file):
    app = run_app()
    for box in app.sidebar.checkbox:
        box.uncheck()
    app.sidebar.button[0].click().run()

    assert "at least one" in app.sidebar.error[0].value
    assert not os.path.exists(settings_file)


def test_jobs_table_shows_the_source(db):
    mark_seen([job("cea:42", "A CEA job", 78), job("inria:1", "An Inria job", 60, letter=None)])
    app = run_app()
    assert set(app.dataframe[0].value["Source"]) == {"CEA", "Inria"}
