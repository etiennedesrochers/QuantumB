"""Project management API routes."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Body, File, UploadFile
from fastapi.responses import FileResponse

from ...services import project_service

router = APIRouter(prefix="/api", tags=["projects"])


@router.get("/projects")
def list_projects() -> list[dict[str, Any]]:
    return project_service.list_projects()


@router.get("/projects/{project_id}")
def get_project(project_id: str) -> dict[str, Any]:
    return project_service.get_project(project_id)


@router.post("/projects")
def create_project(payload: dict[str, Any] = Body(...)) -> dict[str, Any]:
    return project_service.save_project(payload)


@router.put("/projects/{project_id}")
def update_project(project_id: str, payload: dict[str, Any] = Body(...)) -> dict[str, Any]:
    return project_service.save_project(payload, project_id=project_id)


@router.delete("/projects/{project_id}")
def delete_project(project_id: str) -> dict[str, str]:
    project_service.delete_project(project_id)
    return {"message": f"Project '{project_id}' deleted."}


@router.post("/projects/import")
async def import_project(file: UploadFile = File(...)) -> dict[str, Any]:
    contents = await file.read()
    return project_service.import_project(file.filename or "project.aepj", contents)


@router.get("/projects/{project_id}/export")
def export_project(project_id: str) -> FileResponse:
    file_path = project_service.get_project_file_path(project_id)
    return FileResponse(
        path=file_path,
        filename=file_path.name,
        media_type="application/json",
    )
