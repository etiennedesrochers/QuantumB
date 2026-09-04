"""Excel workbook lookups (`data_excel/XNNOV-RS-Database.xlsm`)."""

from __future__ import annotations

from typing import Any

from ..legacy_bridge import ensure_legacy_importable
from . import compressor_service
from .errors import ValidationError

ensure_legacy_importable()

import src.core.workbook_manager as workbook_manager  # noqa: E402


def load_table_catalog() -> dict[str, Any]:
    return workbook_manager.load_table_catalog()


def load_compressor_rows() -> list[dict[str, Any]]:
    return workbook_manager.load_compressor_rows()


def load_generator_filters(manufacturer: str | None = None) -> dict[str, Any]:
    return workbook_manager.load_generator_filters(manufacturer=manufacturer)


def load_circuits_for_selection(
    capacity: float | None,
    manufacturer: str,
    tension: str,
) -> dict[str, Any]:
    """Return circuits/compressors for a selection, templates already resolved."""
    manufacturer = (manufacturer or "").strip()
    tension = (tension or "").strip()
    if capacity is None or not manufacturer or not tension:
        raise ValidationError(
            "Missing required parameters: capacity, manufacturer, tension"
        )

    payload = workbook_manager.load_circuits_for_selection(
        capacity=float(capacity),
        manufacturer=manufacturer,
        tension=tension,
    )
    return compressor_service.attach_library_templates(payload)
