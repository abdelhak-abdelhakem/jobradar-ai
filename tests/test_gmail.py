"""Sending email. The fake Gmail server comes from conftest.py, so tests never send real email."""
import smtplib

import pytest

from src.utils import gmail

REAL_SMTP_SSL = smtplib.SMTP_SSL   # read when this file is imported, before any fixture replaces it


def test_email_is_sent_to_yourself_over_ssl(smtp):
    assert gmail.send_email("JobRadar digest", "Three new jobs.") is True

    assert smtp.connections == [("smtp.gmail.com", 465)]
    assert smtp.logged_in == ("bot@gmail.com", "SECRET-APP-PASSWORD")
    [message] = smtp.sent
    assert message["Subject"] == "JobRadar digest"
    assert message["From"] == message["To"] == "bot@gmail.com"
    assert message.get_content().strip() == "Three new jobs."   # text only: no HTML was given


def test_html_is_sent_with_a_plain_text_fallback(smtp):
    assert gmail.send_email("Digest", "Plain version", "<p>HTML version</p>") is True

    [message] = smtp.sent
    assert message.get_content_type() == "multipart/alternative"
    assert message.get_body(("plain",)).get_content().strip() == "Plain version"
    assert message.get_body(("html",)).get_content().strip() == "<p>HTML version</p>"


@pytest.mark.parametrize("missing", ["GMAIL_ADDRESS", "GMAIL_APP_PASSWORD"])
def test_missing_credentials_send_nothing(smtp, monkeypatch, missing):
    monkeypatch.setattr(gmail, missing, None)
    assert gmail.send_email("Subject", "Text") is False
    assert smtp.connections == []   # never connected


def test_wrong_password_returns_false_without_printing_details(smtp, capsys):
    smtp.down = True
    assert gmail.send_email("Subject", "Text") is False
    output = capsys.readouterr().out
    assert "SMTPAuthenticationError" in output
    assert "bot@gmail.com" not in output and "SECRET" not in output


def test_network_error_returns_false(monkeypatch):
    def unreachable(*args, **kwargs):
        raise TimeoutError("timed out")

    monkeypatch.setattr(gmail.smtplib, "SMTP_SSL", unreachable)
    assert gmail.send_email("Subject", "Text") is False


def test_every_test_uses_the_fake_gmail_server():
    assert smtplib.SMTP_SSL is not REAL_SMTP_SSL
