"""Controller (module) listing and the I/O list a selection would produce.

The I/O list is computed by the real engine (`CLIGenerator`), not reimplemented,
so the preview always matches what generation puts on the drawings.
"""

from __future__ import annotations

import math
import shutil
import tempfile
from pathlib import Path
from typing import Any

from ..legacy_bridge import ensure_legacy_importable
from . import generation_service
from .errors import ValidationError

ensure_legacy_importable()

import src.core.module_manager as module_manager  # noqa: E402

_IO_FIELDS = (
    "tag",
    "description",
    "io_type",
    "address",
    "number",
    "signal_type",
    "signal_category",
    "io_type_name",
    "circuit_name",
    "circuit_no",
    "template_name",
)


def list_controllers() -> list[dict[str, Any]]:
    """Controllers are the modules in `modules_library.json`."""
    return [
        {
            "name": module.get("name", ""),
            "company": module.get("company", ""),
            "description": module.get("description", ""),
            "template": module.get("template", ""),
            "inputs": len(module.get("inputs") or []),
            "outputs": len(module.get("outputs") or []),
        }
        for module in module_manager.load_modules()
    ]


def _controller_pages(controller: dict[str, Any] | None, inputs: int, outputs: int) -> int:
    """Same rule as `CLIGenerator.generate()`: one page per full module load."""
    if not controller:
        return 0
    pages = 1
    if controller["inputs"] and inputs:
        pages = max(pages, math.ceil(inputs / controller["inputs"]))
    if controller["outputs"] and outputs:
        pages = max(pages, math.ceil(outputs / controller["outputs"]))
    return pages


def preview_ios(
    payload: dict,
    controller: str | None = None,
    machine_type: str | None = None,
) -> dict[str, Any]:
    """Return the I/O list (with addresses) the selection would generate."""
    if not isinstance(payload, dict):
        raise ValidationError("Selection payload must be a JSON object")
    if not payload.get("circuits"):
        raise ValidationError("No circuits defined in selection data")

    work_dir = Path(tempfile.mkdtemp(prefix="quantumb_io_"))
    try:
        output_dir = work_dir / "output"
        output_dir.mkdir()
        generator, project_dict = generation_service.build_generator(
            payload, work_dir, output_dir, "dxf", controller, machine_type
        )

        # Ordering is already wired into the generator, so addresses follow it.
        items = generator._build_generation_io_items(project_dict["project_circuits"])
        prefix = generation_service.machine_prefix(project_dict["settings"])
        generator._assign_io_addresses(items, prefix)

        active = generator.modules[0] if generator.modules else None
    finally:
        shutil.rmtree(work_dir, ignore_errors=True)

    inputs = sum(1 for item in items if item.io_type == "Input")
    outputs = len(items) - inputs
    active_summary = next(
        (c for c in list_controllers() if active and c["name"] == active.get("name")), None
    )

    return {
        "controller": active_summary,
        "machine_type": machine_type or "",
        "machine_prefix": prefix,
        "summary": {
            "total": len(items),
            "inputs": inputs,
            "outputs": outputs,
            "reserved": sum(1 for item in items if item.description == "Reserved"),
            "controller_pages": _controller_pages(active_summary, inputs, outputs),
        },
        "items": [{field: getattr(item, field, "") for field in _IO_FIELDS} for item in items],
    }
