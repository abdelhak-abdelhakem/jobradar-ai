"""
User settings chosen in the dashboard, saved in data/settings.json.
A missing or broken file falls back to the defaults, so the pipeline always runs.
Role keywords aren't a setting: they come from the contract type (config.CONTRACTS), so the two can't disagree.
"""
import copy
import json
import os
import re

from src import config

# Every job board the pipeline can scrape, in the order they run: name -> label shown to the user.
SOURCES = {"inria": "Inria", "cnrs": "CNRS", "cea": "CEA"}

# Where the digest is sent: name -> label shown to the user.
CHANNELS = {"telegram": "Telegram", "gmail": "Gmail"}

# Which strong matches get a letter: every one, or only the best K. Strong matches outside the best K
# aren't recorded, so the next run scores them again and they compete with the new jobs.
DELIVERY_MODES = ("all", "top_k")

# When a systemd timer runs the pipeline (see src/scheduling.py). The day only matters for "weekly".
SCHEDULES = ("off", "daily", "weekly")
WEEKDAYS = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")
SCHEDULE_TIME = re.compile(r"([01][0-9]|2[0-3]):[0-5][0-9]")   # 24-hour HH:MM

DEFAULT_SETTINGS = {
    "sources": list(SOURCES),
    "channels": ["telegram"],
    "contract_type": config.DEFAULT_CONTRACT,
    "domain_keywords": list(config.DOMAIN_KEYWORDS),
    "delivery": "all",
    "top_k": 5,
    "schedule": "off",
    "schedule_day": "Mon",
    "schedule_time": "08:00",
}


def is_contract(value) -> bool:
    """Checks the type first: a list or dict from a broken file can't be looked up in a dict."""
    return isinstance(value, str) and value in config.CONTRACTS


def default_settings() -> dict:
    """A fresh copy of the defaults, so callers can change it without changing DEFAULT_SETTINGS."""
    return copy.deepcopy(DEFAULT_SETTINGS)


def is_top_k(value) -> bool:
    """True for a whole number from 1 to MAX_TOP_K. bool is a subclass of int in Python, so it's excluded."""
    return isinstance(value, int) and not isinstance(value, bool) and 1 <= value <= config.MAX_TOP_K


def is_schedule_time(value) -> bool:
    return isinstance(value, str) and SCHEDULE_TIME.fullmatch(value) is not None


def clean_choices(values, known: dict) -> list[str]:
    """Keeps known names, without duplicates, in the standard order of known."""
    if not isinstance(values, list):
        return []
    return [name for name in known if name in values]


def clean_sources(sources) -> list[str]:
    return clean_choices(sources, SOURCES)


def clean_keywords(keywords) -> list[str]:
    """Keeps the user's keywords, stripped, without empty ones or duplicates, in their order."""
    if not isinstance(keywords, list):
        return []
    cleaned = []
    for keyword in keywords:
        if not isinstance(keyword, str):
            continue
        keyword = keyword.strip()
        if keyword and keyword not in cleaned:
            cleaned.append(keyword)
    return cleaned


def load_settings(path: str | None = None) -> dict:
    """Each setting is checked on its own: a broken one falls back to its default, the others are kept."""
    path = path or config.SETTINGS_PATH
    try:
        with open(path, encoding="utf-8") as f:
            saved = json.load(f)
    except FileNotFoundError:
        return default_settings()
    except (OSError, json.JSONDecodeError) as e:
        print(f"[!] Could not read {path} ({e}). Using the default settings.")
        return default_settings()

    if not isinstance(saved, dict):
        print(f"[!] {path} doesn't hold settings. Using the default settings.")
        return default_settings()

    settings = default_settings()

    sources = clean_sources(saved.get("sources"))
    if sources:
        settings["sources"] = sources
    else:
        print(f"[!] No valid source in {path}. Using all sources.")

    channels = clean_choices(saved.get("channels"), CHANNELS)
    if channels:
        settings["channels"] = channels
    elif "channels" in saved:
        print(f"[!] No valid channel in {path}. Using Telegram.")

    # Missing keys are normal in files saved before a setting existed, so only a broken value is reported.
    # Files saved before role keywords came from the contract type may hold role_keywords; it's ignored.
    contract_type = saved.get("contract_type")
    if is_contract(contract_type):
        settings["contract_type"] = contract_type
    elif "contract_type" in saved:
        print(f"[!] Unknown contract type in {path}. Using {config.DEFAULT_CONTRACT}.")

    domain_keywords = clean_keywords(saved.get("domain_keywords"))
    if domain_keywords:
        settings["domain_keywords"] = domain_keywords
    elif "domain_keywords" in saved:
        print(f"[!] No valid domain_keywords in {path}. Using the default keywords.")

    checks = (
        ("delivery", lambda value: value in DELIVERY_MODES),
        ("top_k", is_top_k),
        ("schedule", lambda value: value in SCHEDULES),
        ("schedule_day", lambda value: value in WEEKDAYS),
        ("schedule_time", is_schedule_time),
    )
    for name, is_valid in checks:
        value = saved.get(name)
        if is_valid(value):
            settings[name] = value
        elif name in saved:
            print(f"[!] Invalid {name} in {path}. Using {settings[name]}.")

    return settings


def save_settings(
    sources: list[str] | None = None,
    channels: list[str] | None = None,
    domain_keywords: list[str] | None = None,
    contract_type: str | None = None,
    delivery: str | None = None,
    top_k: int | None = None,
    schedule: str | None = None,
    schedule_day: str | None = None,
    schedule_time: str | None = None,
    path: str | None = None,
) -> dict:
    """
    Saves the settings that are given and keeps the saved value of the others, then returns them all.
    Raises ValueError if a given setting is empty after cleaning, or the contract type is unknown.
    """
    path = path or config.SETTINGS_PATH
    settings = load_settings(path)

    # None means "not given, keep the saved value". An empty list means the user cleared it, which is an error.
    if sources is not None:
        settings["sources"] = clean_sources(sources)
        if not settings["sources"]:
            raise ValueError("Select at least one source.")

    if channels is not None:
        settings["channels"] = clean_choices(channels, CHANNELS)
        if not settings["channels"]:
            raise ValueError("Select at least one channel.")

    if contract_type is not None:
        if not is_contract(contract_type):
            raise ValueError(f"Unknown contract type: {contract_type}.")
        settings["contract_type"] = contract_type

    if delivery is not None:
        if delivery not in DELIVERY_MODES:
            raise ValueError(f"Unknown delivery mode: {delivery}.")
        settings["delivery"] = delivery

    if top_k is not None:
        if not is_top_k(top_k):
            raise ValueError(f"K must be a whole number from 1 to {config.MAX_TOP_K}.")
        settings["top_k"] = top_k

    if schedule is not None:
        if schedule not in SCHEDULES:
            raise ValueError(f"Unknown schedule: {schedule}.")
        settings["schedule"] = schedule

    if schedule_day is not None:
        if schedule_day not in WEEKDAYS:
            raise ValueError(f"Unknown day: {schedule_day}.")
        settings["schedule_day"] = schedule_day

    if schedule_time is not None:
        if not is_schedule_time(schedule_time):
            raise ValueError("The time must be in 24-hour HH:MM format, such as 08:00.")
        settings["schedule_time"] = schedule_time

    if domain_keywords is not None:
        settings["domain_keywords"] = clean_keywords(domain_keywords)
        if not settings["domain_keywords"]:
            raise ValueError("Enter at least one domain keyword.")

    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(settings, f, indent=2, ensure_ascii=False)
    return settings
