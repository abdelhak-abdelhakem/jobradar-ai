import html
import time

import requests

from src.config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID

MAX_MESSAGE_LENGTH = 4096


def send_html(text: str, _retry: bool = True) -> bool:
    """Sends one message that is already valid Telegram HTML. Returns True if it was delivered."""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("⚠️ Telegram credentials missing. Skipping notification.")
        return False

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": text,
        "parse_mode": "HTML",
        "link_preview_options": {"is_disabled": True},
    }

    try:
        response = requests.post(url, json=payload, timeout=10)
    except requests.RequestException as e:
        # Only the error type is printed, because the message includes the URL with the bot token.
        print(f"  [!] Error sending Telegram message: {type(e).__name__}")
        return False

    if response.status_code == 429 and _retry:
        retry_after = response.json().get("parameters", {}).get("retry_after", 1)
        time.sleep(retry_after)
        return send_html(text, _retry=False)

    if not response.ok:
        print(f"  [!] Telegram rejected a message: {response.status_code} {response.text[:200]}")
        return False
    return True


def split_text(text: str, limit: int = MAX_MESSAGE_LENGTH) -> list[str]:
    """Splits plain text so each escaped part fits in one message, preferring line and word breaks."""
    parts = []
    rest = text.strip()
    while len(html.escape(rest)) > limit:
        end = min(len(rest), limit)
        while len(html.escape(rest[:end])) > limit:
            end -= 1
        cut = max(rest.rfind("\n", 0, end), rest.rfind(" ", 0, end))
        if cut < end // 2:
            cut = end
        parts.append(rest[:cut].strip())
        rest = rest[cut:].strip()
    if rest:
        parts.append(rest)
    return parts


def send_plain(text: str) -> bool:
    """Escapes and sends plain text, using several messages if needed. Returns True if all arrived."""
    results = [send_html(html.escape(part)) for part in split_text(text)]
    return all(results)


def send_lines(lines: list[str]) -> bool:
    """Sends lines of Telegram HTML, grouped into messages so that no tag gets split."""
    messages = []
    current = ""
    for line in lines:
        candidate = f"{current}\n{line}" if current else line
        if len(candidate) > MAX_MESSAGE_LENGTH and current:
            messages.append(current)
            current = line
        else:
            current = candidate
    if current:
        messages.append(current)
    results = [send_html(message) for message in messages]
    return all(results)
