"""
Global rules library: a list of rules that users refer to when working on
templates.  Stored as a plain JSON file next to this module so it persists
independently of any single project.

Each rule is a dict with the keys:
    name        : str   (required, unique label)
    description : str
"""
from __future__ import annotations

import json
from pathlib import Path

RULES_PATH = Path(__file__).parent / "rules_library.json"


def load_rules() -> list[dict]:
    """Return all rules from the library as a list of dicts.

    Returns an empty list when the file does not yet exist or cannot be read.
    """
    try:
        if RULES_PATH.exists():
            return json.loads(RULES_PATH.read_text(encoding="utf-8"))
    except Exception:
        pass
    return []


def save_rules(rules: list[dict]) -> tuple[bool, str]:
    """Persist *rules* (list of dicts) to disk.

    Returns (success, message).
    """
    try:
        RULES_PATH.write_text(
            json.dumps(list(rules), indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        return True, f"Rules saved to {RULES_PATH}"
    except Exception as exc:
        return False, str(exc)
