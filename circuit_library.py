"""
Global circuit library: saves and loads Circuit definitions shared across
all projects.  The library is stored as a plain JSON file next to this
module so it persists independently of any single project file.
"""
from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

LIBRARY_PATH = Path(__file__).parent / "circuit_library.json"


def load_library() -> list[dict]:
    """Return all circuits from the library as a list of dicts.

    Returns an empty list when the file does not yet exist or cannot be read.
    """
    try:
        if LIBRARY_PATH.exists():
            return json.loads(LIBRARY_PATH.read_text(encoding="utf-8"))
    except Exception:
        pass
    return []


def save_library(circuits: list) -> tuple[bool, str]:
    """Persist *circuits* (list of Circuit dataclasses or dicts) to disk.

    Returns (success, message).
    """
    try:
        data = [
            asdict(c) if hasattr(c, "__dataclass_fields__") else dict(c)
            for c in circuits
        ]
        LIBRARY_PATH.write_text(
            json.dumps(data, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        return True, f"Library saved to {LIBRARY_PATH}"
    except Exception as exc:
        return False, str(exc)
