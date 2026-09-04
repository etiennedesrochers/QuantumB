"""In-process drawing generation from a selection payload.

Replaces the legacy web server's `subprocess -> app.py --generate-from-selection`
round trip: the same `selection_adapter` + `CLIGenerator` code is called
directly, so no temp file lands in the repo root and no interpreter is spawned.
"""

from __future__ import annotations

import json
import shutil
import tempfile
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterator

from ..legacy_bridge import ensure_legacy_importable
from . import order_service
from .errors import GenerationError, NotFoundError, ValidationError
from .template_resolver import CircuitTemplateManager

ensure_legacy_importable()

import src.core.project_manager as pm  # noqa: E402
import src.core.selection_adapter as sa  # noqa: E402
from src.cli.cli import CLIGenerator  # noqa: E402

VALID_FORMATS = {"dxf", "dwg", "both"}
ARCHIVE_NAME = "generated_drawings.zip"


@dataclass
class GenerationResult:
    """Outcome of a generation run. `work_dir` holds the zip and the DXFs."""

    zip_path: Path
    files: list[str]
    message: str
    work_dir: Path = field(repr=False)

    def cleanup(self) -> None:
        shutil.rmtree(self.work_dir, ignore_errors=True)


def _validate(payload: object, fmt: str) -> None:
    if not isinstance(payload, dict):
        raise ValidationError("Selection payload must be a JSON object")
    if not payload.get("circuits"):
        raise ValidationError("No circuits defined in selection data")
    if fmt not in VALID_FORMATS:
        raise ValidationError(f"format must be one of {sorted(VALID_FORMATS)}")


def machine_prefix(settings: dict) -> str:
    """Mirror `CLIGenerator.generate()`'s prefix rule."""
    return "AHU" if str(settings.get("machine_type", "Regular")).strip() == "AHU" else "CU"


def _apply_controller(generator: CLIGenerator, controller: str | None) -> None:
    """Move the chosen module to the front; the engine always uses `modules[0]`."""
    if not controller:
        return
    for index, module in enumerate(generator.modules):
        if str(module.get("name", "")) == controller:
            generator.modules = [module, *generator.modules[:index], *generator.modules[index + 1:]]
            return
    raise NotFoundError(f"Controller '{controller}' not found in the module library")


def _apply_ordering(generator: CLIGenerator, machine_type: str | None) -> None:
    """Wrap the engine's I/O builder so the ordering workbook drives the list."""
    if not machine_type:
        return

    build = generator._build_generation_io_items
    resolve = generator._resolve_project_circuit_numbers

    def ordered(project_circuits, manual_io_items=None):
        items = build(project_circuits, manual_io_items)
        numbers = resolve(project_circuits)
        names = dict(zip(numbers, project_circuits))
        return order_service.apply_order(items, machine_type, numbers, names)

    generator._build_generation_io_items = ordered


def build_generator(
    payload: dict,
    work_dir: Path,
    output_dir: Path,
    fmt: str = "dxf",
    controller: str | None = None,
    machine_type: str | None = None,
) -> tuple[CLIGenerator, dict]:
    """Turn a selection payload into a ready-to-run `CLIGenerator`.

    Returns the generator and the project dict the selection adapter produced.
    """
    selection_path = work_dir / "selection.json"
    selection_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    success, message, project_dict, dummy_circuits = sa.generate_from_selection(
        str(selection_path)
    )
    if not success:
        raise GenerationError(message)

    if machine_type:
        project_dict["settings"]["machine_type"] = machine_type
        # The ordering workbook numbers circuits 1, 2, 3 …, but the selection
        # adapter sets circuit_number to the circuit *name*. "#" makes the
        # engine auto-number them so `#` placeholders line up.
        for circuit in dummy_circuits:
            circuit.circuit_number = "#"

    project_path = work_dir / "_temp_selection.aepj"
    success, message = pm.save_project(
        str(project_path),
        project_dict["settings"],
        project_dict["project_circuits"],
        project_dict["io_items"],
        project_dict["rungs"],
    )
    if not success:
        raise GenerationError(f"Error saving temporary project: {message}")

    generator = CLIGenerator(
        str(project_path),
        str(output_dir),
        fmt,
        dummy_circuits=dummy_circuits,
    )
    generator.template_mgr = CircuitTemplateManager()
    _apply_controller(generator, controller)
    _apply_ordering(generator, machine_type)
    return generator, project_dict


def generate_from_selection(
    payload: dict,
    fmt: str = "both",
    controller: str | None = None,
    machine_type: str | None = None,
) -> GenerationResult:
    """Generate drawings for *payload* and zip them.

    The caller owns the returned result and must call `cleanup()` when the
    archive has been consumed (or use `generated_archive`).
    """
    _validate(payload, fmt)

    work_dir = Path(tempfile.mkdtemp(prefix="quantumb_gen_"))
    output_dir = work_dir / "output"
    output_dir.mkdir()

    try:
        generator, _ = build_generator(
            payload, work_dir, output_dir, fmt, controller, machine_type
        )
        success, message = generator.generate()
        if not success:
            raise GenerationError(message)

        zip_path = work_dir / ARCHIVE_NAME
        shutil.make_archive(str(zip_path.with_suffix("")), "zip", str(output_dir))

        files = sorted(
            str(path.relative_to(output_dir))
            for path in output_dir.rglob("*")
            if path.is_file()
        )
        return GenerationResult(
            zip_path=zip_path, files=files, message=message, work_dir=work_dir
        )
    except Exception:
        shutil.rmtree(work_dir, ignore_errors=True)
        raise


@contextmanager
def generated_archive(
    payload: dict,
    fmt: str = "both",
    controller: str | None = None,
    machine_type: str | None = None,
) -> Iterator[GenerationResult]:
    """Context manager that cleans up the work dir on exit."""
    result = generate_from_selection(payload, fmt, controller, machine_type)
    try:
        yield result
    finally:
        result.cleanup()
