"""Generation endpoints: I/O preview and the ZIP download."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Query
from fastapi.responses import FileResponse
from starlette.background import BackgroundTask

from ...services import generation_service, io_service, order_service
from ..models import SelectionPayload

router = APIRouter(prefix="/api", tags=["generate"])


@router.get("/controllers", tags=["libraries"])
def list_controllers() -> list[dict[str, Any]]:
    """Controller modules available for generation."""
    return io_service.list_controllers()


@router.get("/machine-types", tags=["libraries"])
def list_machine_types() -> list[str]:
    """Machine types = sheets of the I/O ordering workbook."""
    return order_service.list_machine_types()


@router.get("/machine-types/{machine_type}/order", tags=["libraries"])
def get_order(machine_type: str) -> dict[str, Any]:
    """The front / circuit / back ordering rows for one machine type."""
    return order_service.load_order(machine_type)


@router.post("/io-preview")
def io_preview(
    payload: SelectionPayload,
    controller: str | None = None,
    machine_type: str | None = None,
) -> dict[str, Any]:
    """The I/O list, with addresses, that this selection would generate."""
    return io_service.preview_ios(payload.model_dump(), controller, machine_type)


# Sync `def` so FastAPI runs this CPU-bound ezdxf work in a threadpool.
@router.post("/generate")
def generate(
    payload: SelectionPayload,
    format: str = Query("both"),
    controller: str | None = None,
    machine_type: str | None = None,
    ladders: bool = Query(True),
) -> FileResponse:
    """Generate drawings in-process and return them as a ZIP download."""
    result = generation_service.generate_from_selection(
        payload.model_dump(), format, controller, machine_type, ladders
    )
    return FileResponse(
        result.zip_path,
        media_type="application/zip",
        filename=generation_service.ARCHIVE_NAME,
        background=BackgroundTask(result.cleanup),
    )
