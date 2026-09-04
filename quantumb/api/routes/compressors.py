"""Compressor library CRUD, import/export, workbook sync."""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Response, status

from ...services import compressor_service
from ..models import CompressorCreate, CompressorImport, CompressorUpdate

router = APIRouter(prefix="/api/compressors", tags=["compressors"])


@router.get("")
def list_compressors() -> list[dict[str, Any]]:
    return compressor_service.list_compressors()


@router.post("", status_code=status.HTTP_201_CREATED)
def create_compressor(payload: CompressorCreate) -> dict[str, Any]:
    return compressor_service.create_compressor(payload.model_dump())


@router.post("/sync-workbook")
def sync_workbook() -> dict[str, Any]:
    """Merge workbook compressor rows into the library, keeping templates."""
    return compressor_service.sync_from_workbook()


@router.get("/export")
def export_compressors() -> Response:
    document = compressor_service.export_compressors()
    filename = f"compressors_{datetime.now():%Y%m%d}.json"
    return Response(
        content=json.dumps(document, indent=2, ensure_ascii=False),
        media_type="application/json",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/import")
def import_compressors(payload: CompressorImport) -> dict[str, Any]:
    return compressor_service.import_compressors(payload.compressors, payload.mode)


@router.get("/{compressor_id}")
def get_compressor(compressor_id: int) -> dict[str, Any]:
    return compressor_service.get_compressor(compressor_id)


@router.put("/{compressor_id}")
def update_compressor(compressor_id: int, payload: CompressorUpdate) -> dict[str, Any]:
    data = payload.model_dump(exclude_unset=True)
    return compressor_service.update_compressor(compressor_id, data)


@router.delete("/{compressor_id}")
def delete_compressor(compressor_id: int) -> dict[str, int]:
    return {"deleted": compressor_service.delete_compressor(compressor_id)}
