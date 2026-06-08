"""
Project persistence: save and load the entire application state to/from a
JSON file (.aepj  — AutoCAD Electrical Project JSON).

Schema (all fields optional for forward-compatibility):

{
  "version": 1,
  "settings": {
    "title": str,
    "project": str,
    "drawing_number": str,
    "revision": str,
    "drawn_by": str,
    "paper_size": str
  },
  "project_circuits": [str, ...],   // list of circuit names from the global library; may repeat
  "io_items": [
    {
      "tag": str, "io_type": str, "address": str, "description": str,
      "panel": str, "signal_type": str, "terminal": str, "cable": str,
      "notes": str
    },
    ...
  ],
  "rungs": [
    {
      "rung_number": int,
      "description": str,
      "components": [
        {
          "symbol": str, "tag": str, "description": str,
          "io_tag": str, "tag_source": str, "description_source": str
        },
        ...
      ]
    },
    ...
  ]
}
"""
from __future__ import annotations

import json
from pathlib import Path
from dataclasses import asdict

FILE_EXTENSION = ".aepj"
FILE_FILTER    = f"AutoCAD Electrical Project (*{FILE_EXTENSION});;All files (*.*)"
SCHEMA_VERSION = 1


# ─────────────────────────────────────────────────────────────────────────────
# Save
# ─────────────────────────────────────────────────────────────────────────────

def save_project(path: str, settings: dict, project_circuits: list,
                 io_items: list, rungs: list) -> tuple[bool, str]:
    """
    Serialise all project data to *path*.

    Parameters
    ----------
    path             : destination file path (should end in FILE_EXTENSION)
    settings         : dict with keys title/project/drawing_number/revision/drawn_by/paper_size
    project_circuits : list[str] — circuit names from the global library (may repeat)
    io_items         : list[IOItem]   (dataclasses)
    rungs            : list[Rung]     (dataclasses with nested Component list)

    Returns (success, message).
    """
    try:
        data = {
            "version":         SCHEMA_VERSION,
            "settings":        settings,
            "project_circuits": list(project_circuits),
            "io_items":        [asdict(i) for i in io_items],
            "rungs":           [_rung_to_dict(r) for r in rungs],
        }
        Path(path).write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        return True, f"Project saved to {path}"
    except Exception as exc:
        return False, str(exc)


def _rung_to_dict(rung) -> dict:
    d = asdict(rung)
    return d


# ─────────────────────────────────────────────────────────────────────────────
# Load
# ─────────────────────────────────────────────────────────────────────────────

def _load_project_circuits(raw: dict) -> list[str]:
    """Extract the project circuit list from a raw JSON dict.

    Handles both the new format (``project_circuits``: list of str) and the
    legacy format (``circuits``: list of Circuit dicts) so that old .aepj
    files continue to load correctly.
    """
    if "project_circuits" in raw:
        return [str(x) for x in raw["project_circuits"]]
    # Legacy format: circuits was a list of full Circuit dicts – keep the names.
    legacy = raw.get("circuits", [])
    return [c["name"] for c in legacy if isinstance(c, dict) and "name" in c]


def load_project(path: str) -> tuple[bool, str, dict]:
    """
    Deserialise a project file.

    Returns (success, message, data_dict) where data_dict contains:
        "settings"  : dict
        "circuits"  : list[dict]
        "io_items"  : list[dict]
        "rungs"     : list[dict]
    On failure, data_dict is empty.
    """
    try:
        raw = json.loads(Path(path).read_text(encoding="utf-8"))
        # Basic version guard (future-proof)
        version = raw.get("version", 1)
        if version > SCHEMA_VERSION:
            return False, (
                f"Project was saved with a newer version of the application "
                f"(schema v{version}). Please upgrade."
            ), {}
        data = {
            "settings":        raw.get("settings", {}),
            "project_circuits": _load_project_circuits(raw),
            "io_items":        raw.get("io_items", []),
            "rungs":           raw.get("rungs", []),
        }
        return True, f"Project loaded from {path}", data
    except Exception as exc:
        return False, str(exc), {}
