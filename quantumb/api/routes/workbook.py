"""Excel workbook lookups."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Query

from ...services import workbook_service

router = APIRouter(prefix="/api/workbook", tags=["workbook"])


@router.get("/tables")
def get_tables() -> dict[str, Any]:
    return workbook_service.load_table_catalog()


@router.get("/compressors")
def get_compressors() -> list[dict[str, Any]]:
    return workbook_service.load_compressor_rows()


@router.get("/generator-filters")
def get_generator_filters(manufacturer: str | None = None) -> dict[str, Any]:
    """Capacity/manufacturer/tension options; capacities are manufacturer-scoped."""
    return workbook_service.load_generator_filters(manufacturer=manufacturer)


@router.get("/circuits")
def get_circuits(
    capacity: float = Query(...),
    manufacturer: str = Query(...),
    tension: str = Query(...),
) -> dict[str, Any]:
    return workbook_service.load_circuits_for_selection(capacity, manufacturer, tension)
