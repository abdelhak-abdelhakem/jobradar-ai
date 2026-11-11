"""
User settings chosen in the dashboard, saved in data/settings.json.
A missing or broken file falls back to the defaults, so the pipeline always runs.
"""
import copy
import json
import os

from src import config

# Every job board the pipeline can scrape, in the order they run: name -> label shown to the user.
SOURCES = {"inria": "Inria", "cnrs": "CNRS", "cea": "CEA"}

DEFAULT_SETTINGS = {
    "sources": list(SOURCES),
    "role_keywords": list(config.ROLE_KEYWORDS),
    "domain_keywords": list(config.DOMAIN_KEYWORDS),
}


def default_settings() -> dict:
    """A fresh copy of the defaults, so callers can change it without changing DEFAULT_SETTINGS."""
    return copy.deepcopy(DEFAULT_SETTINGS)


def clean_sources(sources) -> list[str]:
    """Keeps known source names, without duplicates, in the standard order."""
    if not isinstance(sources, list):
        return []
    return [name for name in SOURCES if name in sources]


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

    for name in ("role_keywords", "domain_keywords"):
        keywords = clean_keywords(saved.get(name))
        if keywords:
            settings[name] = keywords
        elif name in saved:
            # Missing keys are normal in files saved before keywords existed, so only a broken value is reported.
            print(f"[!] No valid {name} in {path}. Using the default keywords.")

    return settings


def save_settings(
    sources: list[str] | None = None,
    role_keywords: list[str] | None = None,
    domain_keywords: list[str] | None = None,
    path: str | None = None,
) -> dict:
    """
    Saves the settings that are given and keeps the saved value of the others, then returns them all.
    Raises ValueError if a given setting is empty after cleaning.
    """
    path = path or config.SETTINGS_PATH
    settings = load_settings(path)

    # None means "not given, keep the saved value". An empty list means the user cleared it, which is an error.
    if sources is not None:
        settings["sources"] = clean_sources(sources)
        if not settings["sources"]:
            raise ValueError("Select at least one source.")

    if role_keywords is not None:
        settings["role_keywords"] = clean_keywords(role_keywords)
        if not settings["role_keywords"]:
            raise ValueError("Enter at least one role keyword.")

    if domain_keywords is not None:
        settings["domain_keywords"] = clean_keywords(domain_keywords)
        if not settings["domain_keywords"]:
            raise ValueError("Enter at least one domain keyword.")

    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(settings, f, indent=2, ensure_ascii=False)
    return settings
