"""
Compressor library: user-defined compressor types with associated templates,
shared across all projects via the web interface.

compressor_library.json schema
-------------------------------
[
    {
        "id":           int,
        "name":         str,
        "model":        str,
        "manufacturer": str,
        "capacity":     float,
        "templates": [
            {"id": int, "type": str, "name": str, "scope": "shared" | "per_unit"},
            ...
        ]
    },
    ...
]

``type`` matches one of the template categories managed by
``template_manager`` (regular, controller, io, ladder, ladder_component,
valves). ``scope`` controls how many times the template is instantiated when
a circuit is generated: "per_unit" templates are repeated once per
compressor quantity in a circuit, "shared" templates are only used once.
"""
from __future__ import annotations

import json
from pathlib import Path

_CONFIG_DIR = Path(__file__).resolve().parent.parent.parent / "config"
COMPRESSORS_PATH = _CONFIG_DIR / "compressor_library.json"


def load_compressors() -> list[dict]:
    """Return all compressors from the library. Returns [] on error / missing file."""
    try:
        if COMPRESSORS_PATH.exists():
            return json.loads(COMPRESSORS_PATH.read_text(encoding="utf-8"))
    except Exception:
        pass
    return []


def save_compressors(compressors: list[dict]) -> tuple[bool, str]:
    """Persist *compressors* to disk. Returns (success, message)."""
    try:
        COMPRESSORS_PATH.write_text(
            json.dumps(list(compressors), indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        return True, f"Compressors saved to {COMPRESSORS_PATH}"
    except Exception as exc:
        return False, str(exc)
