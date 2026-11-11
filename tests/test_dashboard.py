import os
import sqlite3

import pytest
from streamlit.testing.v1 import AppTest

from src.agents.graph import compile_graph
from src.agents.state import initial_state
from src.db.seen_jobs import all_seen, backup_path, clear_seen, mark_seen, seen_keys
from src.evaluation.evaluate_scoring import export_labels
from src.config import DOMAIN_KEYWORDS, PHD_ROLE_KEYWORDS, ROLE_KEYWORDS
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
        "contract_type": "internship",
        "rationale": "Good fit <with> *special* characters.",
        "matched_skills": ["Python"],
        "missing_skills": ["C++"],
        "letter": "Dear team,\n\nA letter.\n\nAbdelhak",
        "issues": [],
        **extra,
    }


def click_save(app, form):
    """Clicks the Save button of one sidebar form: contract, sources, or keywords."""
    [button] = [button for button in app.sidebar.button if button.form_id == form]
    button.click().run()
    assert not app.exception


def source_boxes(app):
    return [box for box in app.sidebar.checkbox if box.form_id == "sources"]


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


# Source settings in the sidebar

def test_sidebar_saves_the_chosen_sources(db):
    app = run_app()
    boxes = {box.label: box for box in source_boxes(app)}
    assert all(box.value for box in boxes.values())   # all sources are on by default

    boxes["CNRS"].uncheck()
    click_save(app, "sources")

    assert "Saved" in app.sidebar.success[0].value
    assert load_settings()["sources"] == ["inria", "cea"]
    assert [box.value for box in source_boxes(run_app())] == [True, False, True]


def test_sidebar_refuses_to_save_no_source(db, settings_file):
    app = run_app()
    for box in source_boxes(app):
        box.uncheck()
    click_save(app, "sources")

    assert "at least one" in app.sidebar.error[0].value
    assert not os.path.exists(settings_file)


# Keyword settings in the sidebar

def text_areas(app):
    return {area.label: area for area in app.sidebar.text_area}


def test_sidebar_shows_the_default_keywords(db):
    areas = text_areas(run_app())
    assert areas["Role keywords"].value.splitlines() == ROLE_KEYWORDS
    assert areas["Domain keywords"].value.splitlines() == DOMAIN_KEYWORDS


def test_sidebar_saves_the_keywords(db):
    app = run_app()
    text_areas(app)["Role keywords"].input("PhD\n  thèse \n\nPhD")
    text_areas(app)["Domain keywords"].input("robotics\nAI")
    click_save(app, "keywords")

    assert "Saved" in app.sidebar.success[0].value
    settings = load_settings()
    assert settings["role_keywords"] == ["PhD", "thèse"]
    assert settings["domain_keywords"] == ["robotics", "AI"]
    assert settings["sources"] == ["inria", "cnrs", "cea"]   # saving keywords keeps the sources
    assert text_areas(run_app())["Domain keywords"].value == "robotics\nAI"


def test_sidebar_refuses_to_save_empty_keywords(db, settings_file):
    app = run_app()
    text_areas(app)["Domain keywords"].input("  \n")
    click_save(app, "keywords")

    assert "at least one domain keyword" in app.sidebar.error[0].value
    assert not os.path.exists(settings_file)


def test_saving_sources_keeps_the_saved_keywords(db):
    app = run_app()
    text_areas(app)["Domain keywords"].input("robotics")
    click_save(app, "keywords")

    app = run_app()
    source_boxes(app)[0].uncheck()
    click_save(app, "sources")

    assert load_settings()["sources"] == ["cnrs", "cea"]
    assert load_settings()["domain_keywords"] == ["robotics"]


# Contract type in the sidebar

def test_sidebar_contract_type_defaults_to_internship(db):
    app = run_app()
    assert app.sidebar.selectbox[0].value == "internship"
    assert "PhD searches skip CEA" in app.sidebar.caption[0].value


def test_choosing_phd_resets_the_role_keywords(db):
    app = run_app()
    app.sidebar.selectbox[0].select("phd")
    click_save(app, "contract")

    assert "reset to the PhD defaults" in app.sidebar.success[0].value
    assert load_settings()["contract_type"] == "phd"
    assert text_areas(app)["Role keywords"].value.splitlines() == PHD_ROLE_KEYWORDS


def test_saving_the_same_contract_type_keeps_custom_role_keywords(db):
    app = run_app()
    text_areas(app)["Role keywords"].input("my own word")
    click_save(app, "keywords")

    app = run_app()
    click_save(app, "contract")

    assert app.sidebar.success[0].value == "Saved."
    assert load_settings()["role_keywords"] == ["my own word"]


def test_jobs_show_their_contract_type(db):
    mark_seen([job("cnrs:1", "A PhD", 78, contract_type="phd"), job("inria:1", "An internship", 60, letter=None)])
    app = run_app()
    assert list(app.dataframe[0].value["Contract"]) == ["PhD", "Internship"]
    assert "Contract: PhD" in app.caption[1].value


# Clearing the history

def history_form(app):
    [box] = [box for box in app.sidebar.checkbox if box.form_id == "history"]
    [button] = [button for button in app.sidebar.button if button.form_id == "history"]
    return box, button


def test_clearing_needs_the_confirmation_box(db):
    mark_seen([job()])
    app = run_app()
    _, button = history_form(app)
    button.click().run()

    assert "confirm" in app.sidebar.error[0].value
    assert len(all_seen()) == 1


def test_clearing_deletes_the_history_and_keeps_a_backup(db):
    mark_seen([job("inria:1"), job("inria:2")])
    app = run_app()
    box, button = history_form(app)
    box.check()
    button.click().run()

    assert not app.exception
    assert "Cleared 2 jobs" in app.sidebar.success[0].value
    assert all_seen() == []
    assert "No results yet" in app.info[0].value
    assert len(all_seen(backup_path(db))) == 2
    assert seen_keys() == set()   # the next run scores these jobs again


def test_clearing_an_empty_history_keeps_the_previous_backup(db):
    mark_seen([job()])
    assert clear_seen() == 1
    assert clear_seen() == 0
    assert len(all_seen(backup_path(db))) == 1


def test_clear_button_is_off_when_there_is_no_history(db):
    _, button = history_form(run_app())
    assert button.disabled


def test_jobs_table_shows_the_source(db):
    mark_seen([job("cea:42", "A CEA job", 78), job("inria:1", "An Inria job", 60, letter=None)])
    app = run_app()
    assert set(app.dataframe[0].value["Source"]) == {"CEA", "Inria"}
