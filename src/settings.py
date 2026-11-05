"""
User settings chosen in the dashboard, saved in data/settings.json.
A missing or broken file falls back to the defaults, so the pipeline always runs.
"""
import json
import os

from src import config

# Every job board the pipeline can scrape, in the order they run: name -> label shown to the user.
SOURCES = {"inria": "Inria", "cnrs": "CNRS", "cea": "CEA"}

DEFAULT_SETTINGS = {"sources": list(SOURCES)}


def clean_sources(sources) -> list[str]:
    """Keeps known source names, without duplicates, in the standard order."""
    if not isinstance(sources, list):
        return []
    return [name for name in SOURCES if name in sources]


def load_settings(path: str | None = None) -> dict:
    path = path or config.SETTINGS_PATH
    try:
        with open(path, encoding="utf-8") as f:
            saved = json.load(f)
    except FileNotFoundError:
        return dict(DEFAULT_SETTINGS)
    except (OSError, json.JSONDecodeError) as e:
        print(f"[!] Could not read {path} ({e}). Using the default settings.")
        return dict(DEFAULT_SETTINGS)

    sources = clean_sources(saved.get("sources") if isinstance(saved, dict) else None)
    if not sources:
        print(f"[!] No valid source in {path}. Using all sources.")
        sources = DEFAULT_SETTINGS["sources"]
    return {"sources": sources}


def save_settings(sources: list[str], path: str | None = None) -> dict:
    """Saves the settings and returns them. Raises ValueError if no known source is selected."""
    path = path or config.SETTINGS_PATH
    sources = clean_sources(sources)
    if not sources:
        raise ValueError("Select at least one source.")

    settings = {"sources": sources}
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(settings, f, indent=2)
    return settings
