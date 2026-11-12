"""
Sends email through Gmail's SMTP server, logged in with an App Password, never the account password.
Create one in your Google account (Security > App passwords) and put it in .env as GMAIL_APP_PASSWORD.
"""
import smtplib
from email.message import EmailMessage

from src.config import GMAIL_ADDRESS, GMAIL_APP_PASSWORD

SMTP_HOST = "smtp.gmail.com"
SMTP_PORT = 465   # SMTP over SSL: the connection is encrypted from the start


def send_email(subject: str, text: str, html: str | None = None) -> bool:
    """
    Sends one email to yourself. Returns True if Gmail accepted it.
    With html, the email holds both versions: mail apps show the HTML, and fall back to the text.
    A failure returns False instead of raising, so one failed channel doesn't stop the others.
    """
    if not GMAIL_ADDRESS or not GMAIL_APP_PASSWORD:
        print("⚠️ Gmail credentials missing. Skipping email.")
        return False

    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = GMAIL_ADDRESS
    message["To"] = GMAIL_ADDRESS
    message.set_content(text)
    if html is not None:
        message.add_alternative(html, subtype="html")

    try:
        with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT, timeout=30) as server:
            server.login(GMAIL_ADDRESS, GMAIL_APP_PASSWORD)
            server.send_message(message)
    except (smtplib.SMTPException, OSError) as e:
        # Only the error type is printed: a login error can echo account details back.
        print(f"  [!] Error sending email: {type(e).__name__}")
        return False
    return True
