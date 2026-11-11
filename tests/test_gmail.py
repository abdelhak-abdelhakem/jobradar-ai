"""Sending email. smtplib is replaced with a fake server, so tests never send real email."""
import smtplib

import pytest

from src.utils import gmail


class FakeSMTP:
    """Stands in for smtplib.SMTP_SSL and records what the code did with it."""

    def __init__(self, host, port, timeout):
        self.address = (host, port)
        FakeSMTP.last = self

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def login(self, user, password):
        if FakeSMTP.wrong_password:
            raise smtplib.SMTPAuthenticationError(535, b"Username and Password not accepted for bot@gmail.com")
        self.logged_in = (user, password)

    def send_message(self, message):
        self.sent = message


@pytest.fixture
def smtp(monkeypatch):
    FakeSMTP.last = None
    FakeSMTP.wrong_password = False
    monkeypatch.setattr(gmail.smtplib, "SMTP_SSL", FakeSMTP)
    monkeypatch.setattr(gmail, "GMAIL_ADDRESS", "bot@gmail.com")
    monkeypatch.setattr(gmail, "GMAIL_APP_PASSWORD", "SECRET-APP-PASSWORD")
    return FakeSMTP


def test_email_is_sent_to_yourself_over_ssl(smtp):
    assert gmail.send_email("JobRadar digest", "Three new jobs.") is True

    server = smtp.last
    assert server.address == ("smtp.gmail.com", 465)
    assert server.logged_in == ("bot@gmail.com", "SECRET-APP-PASSWORD")
    assert server.sent["Subject"] == "JobRadar digest"
    assert server.sent["From"] == server.sent["To"] == "bot@gmail.com"
    assert server.sent.get_content().strip() == "Three new jobs."


@pytest.mark.parametrize("missing", ["GMAIL_ADDRESS", "GMAIL_APP_PASSWORD"])
def test_missing_credentials_send_nothing(smtp, monkeypatch, missing):
    monkeypatch.setattr(gmail, missing, None)
    assert gmail.send_email("Subject", "Text") is False
    assert smtp.last is None   # never connected


def test_wrong_password_returns_false_without_printing_details(smtp, capsys):
    smtp.wrong_password = True
    assert gmail.send_email("Subject", "Text") is False
    output = capsys.readouterr().out
    assert "SMTPAuthenticationError" in output
    assert "bot@gmail.com" not in output and "SECRET" not in output


def test_network_error_returns_false(smtp, monkeypatch):
    def unreachable(*args, **kwargs):
        raise TimeoutError("timed out")

    monkeypatch.setattr(gmail.smtplib, "SMTP_SSL", unreachable)
    assert gmail.send_email("Subject", "Text") is False
