"""In-process drawing generation from a selection payload.

Replaces the legacy web server's `subprocess -> app.py --generate-from-selection`
round trip: the same `selection_adapter` + `CLIGenerator` code is called
directly, so no temp file lands in the repo root and no interpreter is spawned.
"""

from __future__ import annotations

import json
import math
import shutil
import tempfile
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterator

from ..legacy_bridge import ensure_legacy_importable
from . import ladder_service, library_service, order_service
from .errors import GenerationError, NotFoundError, ValidationError
from .template_resolver import CircuitTemplateManager

ensure_legacy_importable()

import src.core.project_manager as pm  # noqa: E402
import src.core.selection_adapter as sa  # noqa: E402
from src.cli.cli import CLIGenerator  # noqa: E402
from src.core.drawing_generator import DrawingGenerator  # noqa: E402
from src.core.template_manager import TemplateManager, VALVES_TEMPLATES_DIR, convert_folder_dxf_to_dwg  # noqa: E402

VALID_FORMATS = {"dxf", "dwg", "both"}
ARCHIVE_NAME = "generated_drawings.zip"


@dataclass(frozen=True)
class ValveDrawingItem:
    """One valve instance assigned to a specific valve drawing page."""

    valve_type: str
    circuit_name: str
    number: int
    type_index: int


@dataclass
class ValveDrawingCounters:
    """Counters shared by every valve page in one generation run."""

    fuse: int = 0
    control_relay: int = 0
    power_supply: int = 0
    solenoid: int = 0
    safety_device: int = 0


def _valve_substitutions(
    valves: list[ValveDrawingItem],
    valve_page_number: int,
    linked_detail_pages: list[int] | None = None,
) -> dict[str, str | list[str]]:
    """Return substitutions for one valve page and its assigned valves.

    ``valve_page_number`` is page context for valve-specific rules below;
    it is not itself a generic template replacement value.
    """
    type_codes = {"heat": "H", "cool": "C", "reverse": "R"}
    circuit_numbers = [valve.circuit_name for valve in valves]
    valve_labels = [
        f"EEV-{type_codes.get(valve.valve_type.lower(), valve.valve_type.upper())}"
        f"{valve.circuit_name}-{_letter_for_index(valve.type_index)}"
        for valve in valves
    ]
    linked_detail_pages = linked_detail_pages or []
    first_circuit = circuit_numbers[0] if circuit_numbers else ""
    second_circuit = circuit_numbers[1] if len(circuit_numbers) > 1 else ""
    sensor_names = [f"{valve.valve_type.upper()} SENSOR {index}" for index, valve in enumerate(valves, start=1)]
    sensor_tags = [f"{valve.valve_type[:1].upper()}S{index}" for index, valve in enumerate(valves, start=1)]
    substitutions = {
        # The transformer template repeats an unnumbered circuit placeholder.
        "CIRCUIT #": [first_circuit, second_circuit],
        "CIRCUIT #1": first_circuit,
        "CIRCUIT #2": second_circuit,
        "EEV-C#-A": valve_labels[0] if valve_labels else "",
        "EEV-C#-B": valve_labels[1] if len(valve_labels) > 1 else "",
        "EEV#1": valve_labels[0] if valve_labels else "",
        "EEV#2": valve_labels[1] if len(valve_labels) > 1 else "",
        "TEMP SENSOR 1": sensor_names[0] if sensor_names else "",
        "TEMP SENSOR 2": sensor_names[1] if len(sensor_names) > 1 else "",
        "TS1": sensor_tags[0] if sensor_tags else "",
        "TS2": sensor_tags[1] if len(sensor_tags) > 1 else "",
    }

    if linked_detail_pages:
        detail_links = [f"PCTL-{page}BATTIN{index}" for index, page in enumerate(linked_detail_pages, start=1)]
        detail_ground_links = [f"PCTL-{page}BATTG{index}" for index, page in enumerate(linked_detail_pages, start=1)]
        substitutions.update({
            "PCTL-#BATTIN1": detail_links[0],
            "PCTL-#BATTG1": detail_ground_links[0],
            "PCTL-#BATTIN2": detail_links[1] if len(detail_links) > 1 else "",
            "PCTL-#BATTG2": detail_ground_links[1] if len(detail_ground_links) > 1 else "",
        })

    for i, valve in enumerate(valves, start=1):
        substitutions[f"%TEXTVAL{i}-1%"] = valve.valve_type.upper()
        substitutions[f"%TEXTVAL{i}-2%"] = "ECN-N"
        substitutions[f"%TEXTVAL{i}-3%"] = f"{valve.valve_type[:1].upper()}S{valve.number}"
    return substitutions


def _letter_for_index(index: int) -> str:
    """Convert 1-based valve sequence to A, B, ..., Z, AA, AB, ..."""
    result = ""
    while index:
        index, remainder = divmod(index - 1, 26)
        result = chr(ord("A") + remainder) + result
    return result


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


def _capture_io_items(generator: CLIGenerator) -> list:
    """Expose the engine's I/O list to the caller.

    `_assign_io_addresses` mutates the very list `_build_generation_io_items`
    returns, so holding onto it yields fully addressed items once
    `generate()` has run.
    """
    captured: list = []
    build = generator._build_generation_io_items

    def capturing(project_circuits, manual_io_items=None):
        items = build(project_circuits, manual_io_items)
        captured[:] = [items]
        return items

    generator._build_generation_io_items = capturing
    return captured


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


def _generate_ladders(generator: CLIGenerator, settings: dict, io_items: list) -> list[str]:
    """Emit the L pages the CLI engine never produced (GUI-only feature)."""
    prefix = machine_prefix(settings)
    ladder_gen = ladder_service.LadderGenerator(generator.io_types, prefix)
    _, errors = ladder_gen.generate(
        generator.output_dir, generator._build_config(settings), io_items
    )
    return errors


def _generate_valves(
    generator: CLIGenerator, output_dir: Path, settings: dict, payload: dict
) -> tuple[list[str], list[str]]:
    """Generate valve pages from each circuit's valve quantities."""
    circuit_valves = [
        (str(circuit.get("name") or "Circuit"), circuit.get("valves") or {})
        for circuit in payload.get("circuits") or []
        if isinstance(circuit, dict)
    ]
    if not any(circuit_values for _, circuit_values in circuit_valves):
        return [], []

    manufacturer = str(payload.get("manufacturer") or "").strip()
    configurations = library_service.list_valve_configurations()
    configuration = next(
        (item for item in configurations if item.get("manufacturer") == manufacturer),
        None,
    )
    if configuration is None:
        return [], [f"No valve configuration found for manufacturer '{manufacturer}'."]

    first_template = configuration.get("first_page") or configuration.get("template")
    second_template = configuration.get("second_page") or configuration.get("template")
    if not first_template or not second_template:
        return [], [f"Valve configuration for '{manufacturer}' requires first and second page templates."]

    template_manager = TemplateManager(VALVES_TEMPLATES_DIR)
    valves_per_first_page = max(1, int(configuration.get("first_page_psu_shared_by") or 2))
    valves_per_second_page = max(1, int(configuration.get("second_page_valves_per_page") or 2))
    generated: list[str] = []
    errors: list[str] = []
    page_number = 1
    next_valve_number = 1
    counters = ValveDrawingCounters()
    prefix = machine_prefix(settings)

    for circuit_name, quantities in circuit_valves:
        valves: list[ValveDrawingItem] = []
        type_indexes: dict[str, int] = {}
        for valve_type, quantity in quantities.items():
            valve_count = max(0, int(quantity))
            if valve_count == 0:
                continue
            for index in range(valve_count):
                type_indexes[valve_type] = type_indexes.get(valve_type, 0) + 1
                valves.append(ValveDrawingItem(
                    valve_type,
                    circuit_name,
                    next_valve_number + index,
                    type_indexes[valve_type],
                ))
            next_valve_number += valve_count
        if not valves:
            continue

        page_plan = []
        valve_index = 0
        page_in_circuit = 0
        while valve_index < len(valves):
            is_first_page = page_in_circuit % 2 == 0
            template_name = first_template if is_first_page else second_template
            valves_per_page = valves_per_first_page if is_first_page else valves_per_second_page
            page_plan.append((
                template_name,
                valves[valve_index : valve_index + valves_per_page],
                page_number + len(page_plan),
                [],
            ))
            valve_index += valves_per_page
            page_in_circuit += 1

        for template_name, page_valves, current_page_number, linked_detail_pages in page_plan:
            template_doc = template_manager.load_template(template_name)
            if template_doc is None:
                errors.append(f"Valve template '{template_name}' could not be loaded.")
                continue
            page_name = f"V{current_page_number:03d}"
            prepared_template = _apply_valve_substitutions(
                template_doc, page_valves, current_page_number, counters, linked_detail_pages
            )
            output_path = output_dir / f"{page_name}.dxf"
            page_config = generator._build_config(settings)
            page_config.drawing_number = page_name
            ok, message = DrawingGenerator(page_config).generate(
                [],
                str(output_path),
                prepared_template,
                io_items=[],
                controller_number=0,
                machine_prefix=prefix,
            )
            if ok:
                generated.append(page_name)
            else:
                errors.append(f"{circuit_name} {page_name}: {message}")
        page_number += len(page_plan)

    return generated, errors


def _apply_valve_substitutions(
    template_doc: object,
    page_valves: list[ValveDrawingItem],
    valve_page_number: int,
    counters: ValveDrawingCounters,
    linked_detail_pages: list[int] | None = None,
) -> object:
    """Prepare one valve page and advance its run-level drawing counters."""
    import io
    import ezdxf

    substitutions = _valve_substitutions(
        page_valves, valve_page_number, linked_detail_pages
    )
    buffer = io.StringIO()
    template_doc.write(buffer)
    buffer.seek(0)
    copied_doc = ezdxf.read(buffer)
    replacement_indexes: dict[str, int] = {}
    fuse_base: int | None = None
    for entity in copied_doc.modelspace():
        if entity.dxftype() != "INSERT":
            continue
        for attribute in entity.attribs:
            text = attribute.dxf.get("text", "")
            if text in substitutions:
                index = replacement_indexes.get(text, 0)
                replacements = substitutions[text]
                if isinstance(replacements, str):
                    attribute.dxf.text = replacements
                elif index < len(replacements):
                    attribute.dxf.text = replacements[index]
                    replacement_indexes[text] = index + 1
                continue

            if text.startswith("FU!+"):
                if fuse_base is None:
                    fuse_base = counters.fuse + 1
                offset = int(text.split("+", 1)[1])
                fuse_number = fuse_base + offset
                attribute.dxf.text = f"FU{fuse_number}"
                counters.fuse = max(counters.fuse, fuse_number)
            elif text == "FU!":
                if fuse_base is None:
                    fuse_base = counters.fuse + 1
                attribute.dxf.text = f"FU{fuse_base}"
                counters.fuse = max(counters.fuse, fuse_base)
            elif text == "CR!":
                counters.control_relay += 1
                attribute.dxf.text = f"CR{counters.control_relay}"
            elif text == "PS#":
                counters.power_supply += 1
                attribute.dxf.text = f"PS{counters.power_supply}"
            elif text == "SOL#":
                counters.solenoid += 1
                attribute.dxf.text = f"SOL{counters.solenoid}"
            elif text == "SD#":
                counters.safety_device += 1
                attribute.dxf.text = f"SD{counters.safety_device}"
    return copied_doc


def generate_from_selection(
    payload: dict,
    fmt: str = "both",
    controller: str | None = None,
    machine_type: str | None = None,
    ladders: bool = True,
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
        # Ladder pages are drawn after the engine runs, so DWG conversion is
        # deferred to this service instead of happening inside `generate()`.
        generator, project_dict = build_generator(
            payload, work_dir, output_dir, "dxf", controller, machine_type
        )
        captured = _capture_io_items(generator) if ladders else []
        success, message = generator.generate()
        if not success:
            raise GenerationError(message)

        if ladders and captured and captured[0]:
            ladder_errors = _generate_ladders(
                generator, project_dict["settings"], captured[0]
            )
            if ladder_errors:
                message += "\n\n[WARNING] Ladder pages:" + "".join(
                    f"\n  - {error}" for error in ladder_errors
                )

        valve_pages, valve_errors = _generate_valves(
            generator, output_dir, project_dict["settings"], payload
        )
        if valve_pages:
            message += f"\n\nGenerated {len(valve_pages)} valve page(s): {', '.join(valve_pages)}"
        if valve_errors:
            message += "\n\n[WARNING] Valve pages:" + "".join(
                f"\n  - {error}" for error in valve_errors
            )

        if fmt in ("dwg", "both"):
            _, _, conversion_error = convert_folder_dxf_to_dwg(str(output_dir))
            if conversion_error:
                message += f"\n\n[WARNING] DWG conversion: {conversion_error}"

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
    ladders: bool = True,
) -> Iterator[GenerationResult]:
    """Context manager that cleans up the work dir on exit."""
    result = generate_from_selection(payload, fmt, controller, machine_type, ladders)
    try:
        yield result
    finally:
        result.cleanup()
