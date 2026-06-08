"""
Modules library: a list of module definitions shared across all projects.

Two files are maintained side-by-side:
  modules_library.json   — list of module dicts
  module_io_values.json  — flat list of possible value strings for
                           the "other IOs" of any module

Module dict schema
------------------
{
    "name":                str,    # required
    "description":         str,
    "company":             str,
    "inputs":              [{"name": str, "x": float, "y": float}, ...],
    "outputs":             [{"name": str, "x": float, "y": float}, ...],
    "input_commons":       [{"name": str, "x": float, "y": float}, ...],
    "output_commons":      [{"name": str, "x": float, "y": float}, ...],
    "input_common_shared": bool,   # informational only
    "other_ios":           [{"name": str, "description": str, "value": str}, ...]
}
"""
from __future__ import annotations

import json
from pathlib import Path

MODULES_PATH   = Path(__file__).parent / "modules_library.json"
IO_VALUES_PATH = Path(__file__).parent / "module_io_values.json"


# ── modules ──────────────────────────────────────────────────────────────────

def load_modules() -> list[dict]:
    """Return all modules from the library. Returns [] on error / missing file."""
    try:
        if MODULES_PATH.exists():
            return json.loads(MODULES_PATH.read_text(encoding="utf-8"))
    except Exception:
        pass
    return []


def save_modules(modules: list[dict]) -> tuple[bool, str]:
    """Persist *modules* to disk. Returns (success, message)."""
    try:
        MODULES_PATH.write_text(
            json.dumps(list(modules), indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        return True, f"Modules saved to {MODULES_PATH}"
    except Exception as exc:
        return False, str(exc)


# ── IO values ─────────────────────────────────────────────────────────────────

def load_io_values() -> list[str]:
    """Return the list of possible IO values. Returns [] on error / missing file."""
    try:
        if IO_VALUES_PATH.exists():
            return json.loads(IO_VALUES_PATH.read_text(encoding="utf-8"))
    except Exception:
        pass
    return []


def save_io_values(values: list[str]) -> tuple[bool, str]:
    """Persist the IO values list. Returns (success, message)."""
    try:
        IO_VALUES_PATH.write_text(
            json.dumps(list(values), indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        return True, f"IO values saved to {IO_VALUES_PATH}"
    except Exception as exc:
        return False, str(exc)
