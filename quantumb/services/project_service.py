"""Project service for managed project file persistence (.aepj)."""

from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any

from ..legacy_bridge import PROJECTS_DIR, ensure_legacy_importable
from .errors import NotFoundError, ServiceError

ensure_legacy_importable()

import src.core.project_manager as pm  # noqa: E402


def _slugify(text: str) -> str:
    cleaned = re.sub(r"[^\w\s-]", "", str(text)).strip().replace(" ", "_")
    return cleaned or "project"


def _resolve_project_file(project_id: str) -> Path:
    candidates = [
        PROJECTS_DIR / project_id,
        PROJECTS_DIR / f"{project_id}.aepj",
        PROJECTS_DIR / f"{project_id}.json",
    ]
    for p in candidates:
        if p.exists() and p.is_file():
            return p
    raise NotFoundError(f"Project '{project_id}' not found.")


def list_projects() -> list[dict[str, Any]]:
    results = []
    if not PROJECTS_DIR.exists():
        return results

    files = sorted(
        list(PROJECTS_DIR.glob("*.aepj")) + list(PROJECTS_DIR.glob("*.json")),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )

    for p in files:
        try:
            raw = json.loads(p.read_text(encoding="utf-8"))
            settings = raw.get("settings", {})
            name = (
                raw.get("name")
                or settings.get("project_name")
                or settings.get("title")
                or p.stem
            )
            project_number = (
                settings.get("project_number") or settings.get("project") or ""
            )
            mtime = datetime.fromtimestamp(p.stat().st_mtime).isoformat()
            circuits = raw.get("circuits") or raw.get("project_circuits") or []

            results.append({
                "id": p.stem,
                "filename": p.name,
                "name": name,
                "project_number": project_number,
                "revision": settings.get("revision", "A"),
                "drawn_by": settings.get("drawn_by", ""),
                "manufacturer": settings.get("manufacturer", ""),
                "capacity": settings.get("capacity", ""),
                "tension": settings.get("tension") or settings.get("voltage", ""),
                "circuits_count": len(circuits),
                "updated_at": mtime,
                "file_size": p.stat().st_size,
            })
        except Exception:
            continue

    return results


def get_project(project_id: str) -> dict[str, Any]:
    file_path = _resolve_project_file(project_id)
    try:
        raw = json.loads(file_path.read_text(encoding="utf-8"))
        raw["id"] = file_path.stem
        raw["filename"] = file_path.name
        raw["updated_at"] = datetime.fromtimestamp(file_path.stat().st_mtime).isoformat()
        return raw
    except Exception as exc:
        raise ServiceError(f"Error reading project '{project_id}': {exc}") from exc


def save_project(data: dict[str, Any], project_id: str | None = None) -> dict[str, Any]:
    settings = data.get("settings", {})
    name = (
        data.get("name")
        or settings.get("project_name")
        or settings.get("title")
        or project_id
        or "Project"
    )

    if not project_id:
        proj_num = settings.get("project_number") or settings.get("project") or ""
        base_name = f"{proj_num}_{name}" if proj_num else name
        project_id = _slugify(base_name)

    file_path = PROJECTS_DIR / f"{project_id}.aepj"

    # Ensure required structure
    payload = {
        "version": 1,
        "name": name,
        "updated_at": datetime.now().isoformat(),
        "settings": {
            "title": name,
            "project_name": name,
            "project": settings.get("project_number") or settings.get("project", ""),
            "project_number": settings.get("project_number") or settings.get("project", ""),
            "drawing_number": settings.get("drawing_number", ""),
            "revision": settings.get("revision", "A"),
            "drawn_by": settings.get("drawn_by", ""),
            "paper_size": settings.get("paper_size", "A3"),
            "voltage": settings.get("voltage") or settings.get("tension", ""),
            "manufacturer": settings.get("manufacturer", ""),
            "capacity": settings.get("capacity", ""),
            "tension": settings.get("tension", ""),
            "format": settings.get("format", "both"),
        },
        "circuits": data.get("circuits", []),
        "project_circuits": data.get("project_circuits") or [
            c.get("name") for c in data.get("circuits", []) if isinstance(c, dict) and c.get("name")
        ],
        "io_items": data.get("io_items", []),
        "rungs": data.get("rungs", []),
    }

    try:
        file_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
        payload["id"] = file_path.stem
        payload["filename"] = file_path.name
        return payload
    except Exception as exc:
        raise ServiceError(f"Error saving project '{project_id}': {exc}") from exc


def delete_project(project_id: str) -> None:
    file_path = _resolve_project_file(project_id)
    try:
        file_path.unlink()
    except Exception as exc:
        raise ServiceError(f"Error deleting project '{project_id}': {exc}") from exc


def import_project(filename: str, contents: bytes) -> dict[str, Any]:
    try:
        raw = json.loads(contents.decode("utf-8"))
    except Exception as exc:
        raise ServiceError(f"Invalid project file JSON: {exc}") from exc

    stem = Path(filename).stem
    safe_id = _slugify(stem)
    return save_project(raw, project_id=safe_id)


def get_project_file_path(project_id: str) -> Path:
    return _resolve_project_file(project_id)
