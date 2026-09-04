"""Compressor library CRUD, import/export and workbook sync.

Behavior is ported from the legacy Flask routes so the new API stays
payload-compatible; only the HTTP concerns are stripped out.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from ..legacy_bridge import ensure_legacy_importable
from .errors import NotFoundError, ServiceError, ValidationError

ensure_legacy_importable()

import src.core.compressor_manager as compressor_manager  # noqa: E402
import src.core.workbook_manager as workbook_manager  # noqa: E402

_EDITABLE_FIELDS = ("name", "model", "manufacturer", "capacity", "templates")


def _next_id(items: list[dict]) -> int:
    existing: list[int] = []
    for item in items:
        try:
            existing.append(int(item.get("id")))
        except (TypeError, ValueError):
            continue
    return (max(existing) + 1) if existing else 1


def _same_id(value: object, target: int) -> bool:
    try:
        return int(value) == int(target)
    except (TypeError, ValueError):
        return False


def _norm_text(value: object) -> str:
    return str(value or "").strip().lower()


def _to_float(value: object, default: float = 0.0) -> float:
    if value is None or value == "":
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def normalize_templates(raw_templates: object) -> list[dict]:
    """Coerce an incoming template list to the canonical stored shape."""
    if not isinstance(raw_templates, list):
        return []

    normalized: list[dict] = []
    for index, item in enumerate(raw_templates):
        if not isinstance(item, dict):
            continue

        name = str(item.get("name") or "").strip()
        if not name:
            continue

        template_id = item.get("id")
        if template_id in (None, ""):
            template_id = f"tpl-{int(datetime.now().timestamp() * 1000)}-{index}"

        scope = _norm_text(item.get("scope")) or "per_unit"
        if scope not in {"shared", "per_unit"}:
            scope = "per_unit"

        normalized.append(
            {
                "id": template_id,
                "name": name,
                "scope": scope,
                "type": _norm_text(item.get("type")) or "regular",
            }
        )

    return normalized


def _persist(compressors: list[dict]) -> None:
    success, message = compressor_manager.save_compressors(compressors)
    if not success:
        raise ServiceError(message)


def list_compressors() -> list[dict]:
    return compressor_manager.load_compressors()


def get_compressor(compressor_id: int) -> dict:
    for compressor in list_compressors():
        if _same_id(compressor.get("id"), compressor_id):
            return compressor
    raise NotFoundError(f"Compressor {compressor_id} not found")


def create_compressor(data: dict) -> dict:
    name = str(data.get("name") or "").strip()
    if not name:
        raise ValidationError("Compressor name is required")

    compressors = list_compressors()
    new_compressor = {
        "id": _next_id(compressors),
        "name": name,
        "model": data.get("model", ""),
        "manufacturer": data.get("manufacturer", ""),
        "capacity": data.get("capacity", 0),
        "templates": normalize_templates(data.get("templates")),
    }
    compressors.append(new_compressor)
    _persist(compressors)
    return new_compressor


def update_compressor(compressor_id: int, data: dict) -> dict:
    compressors = list_compressors()
    for compressor in compressors:
        if not _same_id(compressor.get("id"), compressor_id):
            continue
        for field in _EDITABLE_FIELDS:
            if field in data:
                compressor[field] = (
                    normalize_templates(data[field]) if field == "templates" else data[field]
                )
        _persist(compressors)
        return compressor
    raise NotFoundError(f"Compressor {compressor_id} not found")


def delete_compressor(compressor_id: int) -> int:
    compressors = list_compressors()
    remaining = [c for c in compressors if not _same_id(c.get("id"), compressor_id)]
    if len(remaining) == len(compressors):
        raise NotFoundError(f"Compressor {compressor_id} not found")
    _persist(remaining)
    return compressor_id


def export_compressors() -> dict[str, Any]:
    """Return the export document (the API layer turns it into a download)."""
    return {
        "version": "1.0",
        "exportDate": datetime.now().isoformat(),
        "compressors": list_compressors(),
    }


def import_compressors(imported: object, mode: str = "merge") -> dict[str, Any]:
    if not isinstance(imported, list):
        raise ValidationError("Invalid file format. Expected a compressors array.")
    if mode not in {"merge", "replace"}:
        raise ValidationError("mode must be 'merge' or 'replace'")

    compressors: list[dict] = [] if mode == "replace" else list_compressors()
    for item in imported:
        if not isinstance(item, dict):
            continue
        item = dict(item)
        item["id"] = _next_id(compressors)
        compressors.append(item)

    _persist(compressors)
    return {"imported": len(imported), "compressors": compressors}


def _best_workbook_model(row: dict) -> str:
    models = row.get("models_by_voltage") or {}
    return (
        str(models.get("400v") or "").strip()
        or str(models.get("200v") or "").strip()
        or str(models.get("600v") or "").strip()
        or str(row.get("skid_model_number") or "").strip()
    )


def sync_from_workbook() -> dict[str, Any]:
    """Merge workbook compressor rows into the library, keeping templates.

    Rows are keyed by skid model name + manufacturer, not model number: many
    distinct compressors share a model number across capacities.
    """
    workbook_rows = workbook_manager.load_compressor_rows()
    compressors = list_compressors()

    by_identity: dict[str, dict] = {}
    by_name: dict[str, dict] = {}
    for comp in compressors:
        name_key = _norm_text(comp.get("name"))
        if not name_key:
            continue
        by_name[name_key] = comp
        by_identity[f"{_norm_text(comp.get('manufacturer'))}|{name_key}"] = comp

    imported_count = updated_count = skipped_count = 0

    for row in workbook_rows:
        name = str(row.get("skid_model_number") or "").strip()
        model = _best_workbook_model(row)
        manufacturer = str(row.get("manufacturer") or "").strip()
        capacity = _to_float(row.get("nominal_capacity"))

        if not name and not model:
            skipped_count += 1
            continue
        name = name or model
        model = model or name

        name_key = _norm_text(name)
        identity_key = f"{_norm_text(manufacturer)}|{name_key}"
        existing = by_identity.get(identity_key) or by_name.get(name_key)

        if existing:
            existing.update(
                {
                    "name": name,
                    "model": model,
                    "manufacturer": manufacturer,
                    "capacity": capacity,
                }
            )
            existing.setdefault("templates", [])
            updated_count += 1
        else:
            existing = {
                "id": _next_id(compressors),
                "name": name,
                "model": model,
                "manufacturer": manufacturer,
                "capacity": capacity,
                "templates": [],
            }
            compressors.append(existing)
            imported_count += 1

        by_identity[identity_key] = existing
        by_name[name_key] = existing

    _persist(compressors)
    return {
        "imported": imported_count,
        "updated": updated_count,
        "skipped": skipped_count,
        "compressors": compressors,
    }


def match_library_compressor(
    workbook_comp: dict,
    compressors: list[dict],
    preferred_manufacturer: str = "",
) -> dict | None:
    """Find the best library match for a workbook compressor row."""
    model_key = _norm_text(workbook_comp.get("model_number"))
    skid_key = _norm_text(workbook_comp.get("skid_model_number"))
    desc_key = _norm_text(workbook_comp.get("description"))
    manufacturer_key = _norm_text(workbook_comp.get("manufacturer")) or _norm_text(
        preferred_manufacturer
    )

    def manufacturer_mismatch(library_comp: dict) -> bool:
        library_manufacturer = _norm_text(library_comp.get("manufacturer"))
        return bool(manufacturer_key and library_manufacturer and manufacturer_key != library_manufacturer)

    # Pass 1-2: manufacturer-scoped name match, then manufacturer-scoped model match.
    for scoped in (True, False):
        for library_comp in compressors:
            if scoped and manufacturer_mismatch(library_comp):
                continue
            library_name = _norm_text(library_comp.get("name"))
            if library_name and library_name in {k for k in (skid_key, desc_key) if k}:
                return library_comp
        for library_comp in compressors:
            if scoped and manufacturer_mismatch(library_comp):
                continue
            library_model = _norm_text(library_comp.get("model"))
            if model_key and library_model and model_key == library_model:
                return library_comp

    return None


def attach_library_templates(payload: dict) -> dict:
    """Resolve each workbook compressor's templates from the shared library."""
    compressors = list_compressors()
    circuits = payload.get("circuits") if isinstance(payload, dict) else None
    if not isinstance(circuits, list) or not compressors:
        return payload

    for circuit in circuits:
        if not isinstance(circuit, dict):
            continue
        preferred_manufacturer = _norm_text(circuit.get("description"))
        circuit_compressors = circuit.get("compressors")
        if not isinstance(circuit_compressors, list):
            continue

        for comp in circuit_compressors:
            if not isinstance(comp, dict):
                continue
            match = match_library_compressor(
                comp, compressors, preferred_manufacturer=preferred_manufacturer
            )
            comp["templates"] = normalize_templates(match.get("templates") if match else [])

    return payload
