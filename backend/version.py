"""App version + changelog. Surfaced via GET /api/version (What's new panel)."""
import os
import json

APP_VERSION = "1.1.0"

_CHANGELOG_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "changelog.json")


def get_changelog() -> list:
    """Release notes, newest first. Editable at data/changelog.json."""
    try:
        with open(_CHANGELOG_PATH, encoding="utf-8") as f:
            rel = json.load(f)
        return rel if isinstance(rel, list) else []
    except Exception:
        return []
