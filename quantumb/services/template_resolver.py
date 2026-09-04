"""Circuit-page template resolution across every category directory.

`CLIGenerator` only ever looks in `templates/ladder/`, so circuit templates of
any other type (in particular the "regular" ones, where all template I/O
metadata actually lives) resolved to nothing: blank pages and an empty I/O list.
This resolver keeps the ladder directory as the first match to preserve the
engine's precedence, then falls back to the other categories.
"""

from __future__ import annotations

from typing import Any

from ..legacy_bridge import ensure_legacy_importable

ensure_legacy_importable()

from src.core.template_manager import (  # noqa: E402
    LADDER_COMPONENT_TEMPLATES_DIR,
    LADDER_TEMPLATES_DIR,
    TEMPLATES_DIR,
    VALVES_TEMPLATES_DIR,
    TemplateManager,
)

_FALLBACK_DIRS = (TEMPLATES_DIR, LADDER_COMPONENT_TEMPLATES_DIR, VALVES_TEMPLATES_DIR)


class CircuitTemplateManager(TemplateManager):
    """A `TemplateManager` for the ladder dir that falls back to the others."""

    def __init__(self) -> None:
        super().__init__(LADDER_TEMPLATES_DIR)
        self._fallbacks = [TemplateManager(directory) for directory in _FALLBACK_DIRS]

    def load_template(self, template_name: str):
        document = super().load_template(template_name)
        if document is not None:
            return document
        for manager in self._fallbacks:
            document = manager.load_template(template_name)
            if document is not None:
                return document
        return None

    def get_template_ios(self, template_name: str) -> list[dict[str, Any]]:
        ios = super().get_template_ios(template_name)
        if ios:
            return ios
        for manager in self._fallbacks:
            ios = manager.get_template_ios(template_name)
            if ios:
                return ios
        return []
