"""Template endpoints: GET listing, upload, delete, and rename."""

from __future__ import annotations

from fastapi import APIRouter, Body, File, UploadFile

from ...services import template_service

router = APIRouter(prefix="/api", tags=["templates"])


@router.get("/templates")
def get_templates() -> dict[str, list[str]]:
    """All templates on disk, grouped by category."""
    return template_service.list_templates()


@router.get("/templates/{category}")
def get_templates_for_category(category: str) -> list[str]:
    return template_service.list_templates_for(category)


@router.post("/templates/{category}/upload")
async def upload_template(category: str, file: UploadFile = File(...)) -> dict[str, str]:
    contents = await file.read()
    name = template_service.upload_template(category, file.filename or "template.dxf", contents)
    return {"name": name, "category": category, "message": f"Template '{name}' uploaded successfully."}


@router.delete("/templates/{category}/{name}")
def delete_template(category: str, name: str) -> dict[str, str]:
    template_service.delete_template(category, name)
    return {"message": f"Template '{name}' deleted."}


@router.post("/templates/{category}/{name}/rename")
def rename_template(category: str, name: str, new_name: str = Body(..., embed=True)) -> dict[str, str]:
    template_service.rename_template(category, name, new_name)
    return {"message": f"Template renamed to '{new_name}'."}


@router.get("/templates/{category}/{name}/info")
def get_template_info(category: str, name: str) -> dict:
    return template_service.get_template_info(category, name)


@router.put("/templates/{category}/{name}/info")
def save_template_info(category: str, name: str, payload: dict = Body(...)) -> dict:
    return template_service.save_template_info(category, name, payload)


@router.get("/templates/{category}/{name}/ios")
def get_template_ios(category: str, name: str) -> list[dict]:
    return template_service.get_template_ios(category, name)


@router.put("/templates/{category}/{name}/ios")
def save_template_ios(category: str, name: str, payload: list[dict] = Body(...)) -> list[dict]:
    return template_service.save_template_ios(category, name, payload)
