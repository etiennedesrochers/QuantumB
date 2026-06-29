"""
Global circuit library: saves and loads Circuit definitions shared across
all projects.  The library is stored as a plain JSON file next to this
module so it persists independently of any single project file.
"""
from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

from models import Template

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


def _convert_templates_for_save(templates: list) -> list:
    """Convert templates list to JSON-serializable format.
    
    Handles both string templates (legacy) and Template objects.
    """
    result = []
    for t in templates:
        if isinstance(t, Template):
            # Convert Template object to dict
            result.append(asdict(t))
        elif isinstance(t, str):
            # Legacy string template
            result.append(t)
        elif isinstance(t, dict):
            # Already a dict
            result.append(t)
        else:
            result.append(t)
    return result


def save_library(circuits: list) -> tuple[bool, str]:
    """Persist *circuits* (list of Circuit dataclasses or dicts) to disk.

    Returns (success, message).
    """
    try:
        data = []
        for c in circuits:
            if hasattr(c, "__dataclass_fields__"):
                circuit_dict = asdict(c)
                # Convert templates to serializable format
                if 'templates' in circuit_dict:
                    circuit_dict['templates'] = _convert_templates_for_save(c.templates)
                data.append(circuit_dict)
            else:
                data.append(dict(c))
        
        LIBRARY_PATH.write_text(
            json.dumps(data, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        return True, f"Library saved to {LIBRARY_PATH}"
    except Exception as exc:
        return False, str(exc)

