import smtplib

import pytest
from langchain_core.runnables import RunnableLambda

from src import scheduling
from src.agents.nodes import draft_letter, score
from src.agents.state import JobMatch, LetterCheck, UnsupportedClaim
from src.utils import gmail, telegram


def make_job(job_id="1", title="Internship in NLP", description="An AI internship.") -> dict:
    return {
        "source": "inria",
        "id": job_id,
        "title": title,
        "company": "Inria",
        "url": f"https://jobs.example/{job_id}",
        "description": description,
    }


def make_match(score_value=80, contract_type="internship", domain_fit="direct") -> JobMatch:
    return JobMatch(
        rationale="Good overlap.",
        matched_skills=["Python"],
        missing_skills=[],
        contract_type=contract_type,
        domain_fit=domain_fit,
        match_score=score_value,
    )


class FakeResponse:
    def __init__(self, status_code=200, payload=None):
        self.status_code = status_code
        self.ok = status_code < 400
        self.text = str(payload or {})
        self._payload = payload or {}

    def json(self):
        return self._payload


class FakeWorld:
    """Stands in for every external service: LLM, Telegram, and the job board."""

    def __init__(self):
        self.jobs = [make_job()]
        self.scores = {}            # text in the job -> score, or an Exception to raise
        self.calls = {"score": 0, "draft": 0, "check": 0, "revise": 0}
        self.score_inputs = []      # what the scoring prompt received, one dict per job
        self.letter = "Dear team,\n\nA truthful letter.\n\nAbdelhak"
        self.unsupported = {}       # text in the letter -> quotes to flag
        self.off_topic_text = None  # letters containing this text are reported as off topic
        self.revised_letter = "Dear team,\n\nA revised letter.\n\nAbdelhak"
        self.draft_error = False
        self.sent = []
        self.telegram_up = True

    def fake_score(self, inputs):
        self.calls["score"] += 1
        self.score_inputs.append(inputs)
        for text, value in self.scores.items():
            if text in inputs["job"]:
                if isinstance(value, Exception):
                    raise value
                if isinstance(value, JobMatch):
                    return value
                return make_match(value)
        return make_match()

    def fake_draft(self, inputs):
        self.calls["draft"] += 1
        if self.draft_error:
            raise RuntimeError("draft failed")
        return self.letter

    def fake_check(self, inputs):
        self.calls["check"] += 1
        claims = []
        for text, quotes in self.unsupported.items():
            if text in inputs["letter"]:
                claims.extend(UnsupportedClaim(quote=q, reason="Not in the profile.") for q in quotes)
        off_topic = self.off_topic_text is not None and self.off_topic_text in inputs["letter"]
        return LetterCheck(unsupported_claims=claims, discusses_job_topic=not off_topic)

    def fake_revise(self, inputs):
        self.calls["revise"] += 1
        return self.revised_letter

    def fake_post(self, url, json, timeout):
        if not self.telegram_up:
            return FakeResponse(400, {"description": "Bad Request"})
        self.sent.append(json["text"])
        return FakeResponse()


@pytest.fixture(autouse=True)
def settings_file(monkeypatch, tmp_path):
    """Every test gets its own settings file, so the real data/settings.json never affects tests."""
    path = str(tmp_path / "settings.json")
    monkeypatch.setattr("src.config.SETTINGS_PATH", path)
    return path


@pytest.fixture(autouse=True)
def run_lock(monkeypatch, tmp_path):
    """Every test gets its own lock file, so a test never waits on, or blocks, a real run."""
    path = str(tmp_path / "run.lock")
    monkeypatch.setattr("src.config.RUN_LOCK_PATH", path)
    return path


class FakeSystemd:
    """Records systemctl commands instead of running them. Set fail to make the next command fail."""

    def __init__(self):
        self.commands = []
        self.fail = False

    def systemctl(self, *args):
        if self.fail:
            raise scheduling.ScheduleError("systemctl failed")
        self.commands.append(args)
        return ""


@pytest.fixture(autouse=True)
def systemd(monkeypatch, tmp_path):
    """Every test gets a fake systemctl and its own unit folder, so no test touches the real systemd."""
    fake = FakeSystemd()
    monkeypatch.setattr(scheduling, "systemctl", fake.systemctl)
    monkeypatch.setattr(scheduling, "UNIT_DIR", str(tmp_path / "systemd-user"))
    return fake


class FakeSMTP:
    """Stands in for smtplib.SMTP_SSL and records every email. Set down to refuse the login."""

    def __init__(self):
        self.sent = []
        self.down = False
        self.connections = []

    def __call__(self, host, port, timeout):
        self.connections.append((host, port))
        return self

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def login(self, user, password):
        if self.down:
            raise smtplib.SMTPAuthenticationError(535, b"Username and Password not accepted for bot@gmail.com")
        self.logged_in = (user, password)

    def send_message(self, message):
        self.sent.append(message)


@pytest.fixture(autouse=True)
def smtp(monkeypatch):
    """Every test gets a fake Gmail server and fake credentials, so no test sends a real email."""
    fake = FakeSMTP()
    monkeypatch.setattr(gmail.smtplib, "SMTP_SSL", fake)
    monkeypatch.setattr(gmail, "GMAIL_ADDRESS", "bot@gmail.com")
    monkeypatch.setattr(gmail, "GMAIL_APP_PASSWORD", "SECRET-APP-PASSWORD")
    return fake


@pytest.fixture
def world(monkeypatch, tmp_path):
    fake = FakeWorld()

    profile = tmp_path / "profile.md"
    profile.write_text("# Abdelhak\nPython, NLP.", encoding="utf-8")
    monkeypatch.setattr("src.config.SEEN_JOBS_DB", str(tmp_path / "seen.sqlite3"))
    monkeypatch.setattr(score, "PROFILE_PATH", str(profile))

    monkeypatch.setattr("src.agents.nodes.scrape.get_inria_jobs", lambda **keywords: fake.jobs)
    monkeypatch.setattr("src.agents.nodes.scrape.get_cnrs_jobs", lambda **keywords: [])
    monkeypatch.setattr("src.agents.nodes.scrape.get_cea_jobs", lambda **keywords: [])
    monkeypatch.setattr(score, "_scoring_chain", lambda: RunnableLambda(fake.fake_score))
    monkeypatch.setattr(draft_letter, "_draft_chain", lambda: RunnableLambda(fake.fake_draft))
    monkeypatch.setattr(draft_letter, "_check_chain", lambda: RunnableLambda(fake.fake_check))
    monkeypatch.setattr(draft_letter, "_revise_chain", lambda: RunnableLambda(fake.fake_revise))

    monkeypatch.setattr(telegram, "TELEGRAM_BOT_TOKEN", "SECRET-TOKEN")
    monkeypatch.setattr(telegram, "TELEGRAM_CHAT_ID", "42")
    monkeypatch.setattr(telegram.requests, "post", fake.fake_post)
    return fake
