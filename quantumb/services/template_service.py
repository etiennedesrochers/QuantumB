"""Template listing and configuration over the legacy `template_manager`."""

from __future__ import annotations

import tempfile
import re
from pathlib import Path

from ..legacy_bridge import ensure_legacy_importable
from .errors import NotFoundError, ServiceError

ensure_legacy_importable()

import src.core.template_manager as template_manager  # noqa: E402


def list_templates() -> dict[str, list[str]]:
    """Return every template on disk grouped by category."""
    try:
        return template_manager.list_templates()
    except Exception as exc:
        raise ServiceError(f"Error listing templates: {exc}") from exc


def list_templates_for(category: str) -> list[str]:
    """Return template names for a single category."""
    templates = list_templates()
    if category not in templates:
        raise NotFoundError(f"Unknown template category: {category}")
    return templates[category]


def upload_template(category: str, filename: str, content: bytes) -> str:
    category_dirs = template_manager._TEMPLATE_TYPE_DIRS
    if category not in category_dirs:
        raise NotFoundError(f"Unknown template category: {category}")

    target_dir = category_dirs[category]
    target_dir.mkdir(parents=True, exist_ok=True)

    suffix = Path(filename).suffix.lower()
    if suffix not in (".dxf", ".dwg"):
        raise ServiceError(f"Unsupported file type: {suffix}. Only .dxf and .dwg are supported.")

    mgr = template_manager.TemplateManager(target_dir)
    template_name = Path(filename).stem

    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(content)
        tmp_path = tmp.name

    try:
        ok, msg = mgr.save_template(tmp_path, template_name)
        if not ok:
            raise ServiceError(msg)
        return template_name
    finally:
        Path(tmp_path).unlink(missing_ok=True)


def delete_template(category: str, template_name: str) -> bool:
    category_dirs = template_manager._TEMPLATE_TYPE_DIRS
    if category not in category_dirs:
        raise NotFoundError(f"Unknown template category: {category}")

    mgr = template_manager.TemplateManager(category_dirs[category])
    ok, msg = mgr.delete_template(template_name)
    if not ok:
        raise NotFoundError(msg)
    return True


def rename_template(category: str, old_name: str, new_name: str) -> bool:
    category_dirs = template_manager._TEMPLATE_TYPE_DIRS
    if category not in category_dirs:
        raise NotFoundError(f"Unknown template category: {category}")

    mgr = template_manager.TemplateManager(category_dirs[category])
    ok, msg = mgr.rename_template(old_name, new_name)
    if not ok:
        raise ServiceError(msg)
    return True


def sort_io_items(ios: list[dict]) -> list[dict]:
    """Sort I/O items by Direction (Input -> Output), Signal Type (Digital -> Analog), and Name."""
    if not isinstance(ios, list):
        return []

    def sort_key(io: dict):
        direction = str(io.get("direction", "")).strip().lower()
        signal_type = str(io.get("signal_type", "")).strip().lower()
        dir_order = 0 if direction == "input" else (1 if direction == "output" else 2)
        sig_order = 0 if signal_type == "digital" else (1 if signal_type == "analog" else 2)
        name = str(io.get("name", "")).strip().lower()
        return (dir_order, sig_order, name)

    return sorted(ios, key=sort_key)


def get_template_info(category: str, template_name: str) -> dict:
    category_dirs = template_manager._TEMPLATE_TYPE_DIRS
    if category not in category_dirs:
        raise NotFoundError(f"Unknown template category: {category}")

    mgr = template_manager.TemplateManager(category_dirs[category])
    ins = mgr.get_insertion_point(template_name)
    offset = mgr.get_offset(template_name)
    ios = sort_io_items(mgr.get_template_ios(template_name))
    try:
        blocks = mgr.get_template_blocks(template_name)
    except Exception:
        blocks = []

    return {
        "name": template_name,
        "category": category,
        "insertion_point": list(ins),
        "offset": list(offset),
        "ios": ios,
        "blocks": blocks,
    }


def save_template_info(category: str, template_name: str, info: dict) -> dict:
    category_dirs = template_manager._TEMPLATE_TYPE_DIRS
    if category not in category_dirs:
        raise NotFoundError(f"Unknown template category: {category}")

    mgr = template_manager.TemplateManager(category_dirs[category])
    if "insertion_point" in info and isinstance(info["insertion_point"], (list, tuple)) and len(info["insertion_point"]) >= 2:
        mgr.set_insertion_point(template_name, float(info["insertion_point"][0]), float(info["insertion_point"][1]))

    if "offset" in info and isinstance(info["offset"], (list, tuple)) and len(info["offset"]) >= 2:
        mgr.set_offset(template_name, float(info["offset"][0]), float(info["offset"][1]))

    if "ios" in info and isinstance(info["ios"], list):
        mgr.set_template_ios(template_name, sort_io_items(info["ios"]))

    return get_template_info(category, template_name)


def get_template_ios(category: str, template_name: str) -> list[dict]:
    category_dirs = template_manager._TEMPLATE_TYPE_DIRS
    if category not in category_dirs:
        raise NotFoundError(f"Unknown template category: {category}")

    mgr = template_manager.TemplateManager(category_dirs[category])
    return sort_io_items(mgr.get_template_ios(template_name))


def get_template_placeholders(category: str, template_name: str) -> list[str]:
    """Return replacement candidates, including placeholders and plain text values."""
    category_dirs = template_manager._TEMPLATE_TYPE_DIRS
    if category not in category_dirs:
        raise NotFoundError(f"Unknown template category: {category}")

    doc = template_manager.TemplateManager(category_dirs[category]).load_template(template_name)
    if doc is None:
        raise NotFoundError(f"Template '{template_name}' not found in {category}")

    values: set[str] = set()
    for entity in doc.modelspace():
        if entity.dxftype() != "INSERT":
            continue
        for attribute in entity.attribs:
            text = attribute.dxf.get("text", "").strip()
            values.update(re.findall(r"%[^%]+%", text))
            if re.fullmatch(r"[A-Za-z][A-Za-z0-9 /#_.-]{1,60}", text):
                values.add(text)
    return sorted(values)


def save_template_ios(category: str, template_name: str, ios: list[dict]) -> list[dict]:
    category_dirs = template_manager._TEMPLATE_TYPE_DIRS
    if category not in category_dirs:
        raise NotFoundError(f"Unknown template category: {category}")

    mgr = template_manager.TemplateManager(category_dirs[category])
    sorted_ios = sort_io_items(ios)
    mgr.set_template_ios(template_name, sorted_ios)
    return sorted_ios
