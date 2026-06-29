"""
Application configuration manager.

General application settings like UI preferences.
Storage: app_config.json next to this module.
"""
from __future__ import annotations

import json
from pathlib import Path

_CONFIG_PATH = Path(__file__).parent / "app_config.json"

# Default configuration
_DEFAULTS = {
    "show_template_preview": True,
}


def load_app_config() -> dict:
    """Load application configuration (creates defaults on first run)."""
    try:
        if _CONFIG_PATH.exists():
            return json.loads(_CONFIG_PATH.read_text(encoding="utf-8"))
    except Exception:
        pass
    # First run – seed with defaults and persist
    save_app_config(_DEFAULTS.copy())
    return _DEFAULTS.copy()


def save_app_config(config: dict) -> None:
    """Persist application configuration."""
    _CONFIG_PATH.write_text(
        json.dumps(config, indent=2, ensure_ascii=False), encoding="utf-8"
    )


def get_show_template_preview() -> bool:
    """Return whether template preview should be shown."""
    config = load_app_config()
    return config.get("show_template_preview", True)


def set_show_template_preview(show: bool) -> None:
    """Set whether template preview should be shown."""
    config = load_app_config()
    config["show_template_preview"] = show
    save_app_config(config)
