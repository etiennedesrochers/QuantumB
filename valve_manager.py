"""
Valve type configuration manager.

Valve *types* (heat, cool, reverse, …) and their associated I/O lists are
global configuration shared across all projects.  Each valve *instance* in a
project only stores a tag, type, description and optional circuit link — the
I/O signals always come from the type definition stored here.

Storage layout (next to this module):
    valve_types.json  — list of type names
    valve_ios.json    — mapping: {type_name: [ValveIO dicts, …]}
"""
from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

from models import ValveIO, DEFAULT_VALVE_TYPES

_TYPES_PATH = Path(__file__).parent / "valve_types.json"
_IOS_PATH   = Path(__file__).parent / "valve_ios.json"


# ── Valve types ───────────────────────────────────────────────────────────────

def load_valve_types() -> list[str]:
    """Return the list of valve type names (creates defaults on first run)."""
    try:
        if _TYPES_PATH.exists():
            return json.loads(_TYPES_PATH.read_text(encoding="utf-8"))
    except Exception:
        pass
    # First run – seed with defaults and persist
    save_valve_types(list(DEFAULT_VALVE_TYPES))
    return list(DEFAULT_VALVE_TYPES)


def save_valve_types(types: list[str]) -> None:
    _TYPES_PATH.write_text(
        json.dumps(types, indent=2, ensure_ascii=False), encoding="utf-8"
    )


# ── Per-type I/O configuration ────────────────────────────────────────────────

def load_valve_ios() -> dict[str, list[dict]]:
    """Return {type_name: [io_dict, …]} for all valve types."""
    try:
        if _IOS_PATH.exists():
            return json.loads(_IOS_PATH.read_text(encoding="utf-8"))
    except Exception:
        pass
    return {}


def save_valve_ios(ios: dict[str, list[dict]]) -> None:
    _IOS_PATH.write_text(
        json.dumps(ios, indent=2, ensure_ascii=False), encoding="utf-8"
    )


def get_ios_for_type(valve_type: str) -> list[ValveIO]:
    """Return the ValveIO list for *valve_type* (empty list if not configured)."""
    raw = load_valve_ios().get(valve_type, [])
    return [ValveIO(**d) for d in raw]


def set_ios_for_type(valve_type: str, ios: list[ValveIO]) -> None:
    """Persist the ValveIO list for *valve_type*."""
    store = load_valve_ios()
    store[valve_type] = [asdict(io) for io in ios]
    save_valve_ios(store)


def rename_type(old_name: str, new_name: str) -> None:
    """Rename a valve type in both the types list and the IO store."""
    types = load_valve_types()
    if old_name in types:
        idx = types.index(old_name)
        types[idx] = new_name
        save_valve_types(types)
    ios = load_valve_ios()
    if old_name in ios:
        ios[new_name] = ios.pop(old_name)
        save_valve_ios(ios)


def delete_type(name: str) -> None:
    """Remove a valve type and its IO config."""
    types = load_valve_types()
    if name in types:
        types.remove(name)
        save_valve_types(types)
    ios = load_valve_ios()
    if name in ios:
        del ios[name]
        save_valve_ios(ios)


# ── Global valve template / quantity config ───────────────────────────────────

_CONFIG_PATH = Path(__file__).parent / "valve_config.json"
_DEFAULT_CONFIG: dict = {"template": "", "quantity": 1}


def load_valve_config() -> dict:
    """Return the global valve config dict (template + quantity)."""
    try:
        if _CONFIG_PATH.exists():
            data = json.loads(_CONFIG_PATH.read_text(encoding="utf-8"))
            return {**_DEFAULT_CONFIG, **data}
    except Exception:
        pass
    return dict(_DEFAULT_CONFIG)


def save_valve_config(config: dict) -> None:
    _CONFIG_PATH.write_text(
        json.dumps(config, indent=2, ensure_ascii=False), encoding="utf-8"
    )
