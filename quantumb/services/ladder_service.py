"""Ladder (L) page generation.

`CLIGenerator.generate()` only emits circuit (E) and controller (C) pages —
ladder pages were a GUI-only feature (`MainWindow._generate_ladder_pages`).
This is a Qt-free port of that logic so the API produces the same L pages.
"""

from __future__ import annotations

import dataclasses
import io as _io
from pathlib import Path
from typing import Any, Iterable

import ezdxf

from ..legacy_bridge import ensure_legacy_importable

ensure_legacy_importable()

from src.core.drawing_generator import DrawingGenerator, LadderConfig  # noqa: E402
from src.core.io_manager import IOItem  # noqa: E402
from src.core.template_manager import (  # noqa: E402
    LADDER_COMPONENT_TEMPLATES_DIR,
    LADDER_TEMPLATES_DIR,
    TemplateManager,
)

# Fallback start position when the ladder template has no insertion point.
_DEFAULT_START_X = 0.0
_DEFAULT_START_Y = 14.5
# Vertical distance between successive rungs (downward).
_COMPONENT_Y_STEP = 2
# Margin above the lowest non-frame INSERT (keeps components off the busbar).
_BOTTOM_MARGIN = 0.5


def ladder_type_map(io_types: Iterable[dict[str, Any]]) -> dict[str, str]:
    """I/O type name -> ladder template name."""
    return {t["name"]: t.get("ladder_type", "") for t in io_types if t.get("ladder_type")}


def component_template_map(io_types: Iterable[dict[str, Any]]) -> dict[str, str]:
    """I/O type name -> ladder component template name."""
    return {
        t["name"]: t.get("ladder_component_template", "")
        for t in io_types
        if t.get("ladder_component_template")
    }


def group_by_ladder_type(
    io_items: Iterable[IOItem], type_map: dict[str, str]
) -> dict[str, list[IOItem]]:
    grouped: dict[str, list[IOItem]] = {}
    for io_item in io_items:
        ladder_type = type_map.get(io_item.io_type_name, "")
        if ladder_type:
            grouped.setdefault(ladder_type, []).append(io_item)
    return grouped


class LadderGenerator:
    """Emits `L###.dxf` pages, one group of components per ladder type."""

    def __init__(self, io_types: list[dict[str, Any]], machine_prefix: str = "CU") -> None:
        self.machine_prefix = machine_prefix
        self._type_map = ladder_type_map(io_types)
        self._component_map = component_template_map(io_types)
        self._ladder_mgr = TemplateManager(LADDER_TEMPLATES_DIR)
        self._component_mgr = TemplateManager(LADDER_COMPONENT_TEMPLATES_DIR)
        # Persistent device counters shared across every page of a run.
        self.ps_count = 1
        self.solcount = 1
        self.sdcount = 1

    # ── planning ────────────────────────────────────────────────────────────

    def _components_per_page(self, ladder_type: str, start_y: float) -> int:
        """Usable vertical space of the template divided by the rung pitch."""
        probe = self._ladder_mgr.load_template(ladder_type)
        base_ys = [
            entity.dxf.insert.y
            for entity in probe.modelspace()
            if entity.dxftype() == "INSERT" and entity.dxf.insert.y > 0.5
        ] if probe is not None else []
        bottom_y = min(base_ys) + _BOTTOM_MARGIN if base_ys else 3.5
        return max(1, int((start_y - bottom_y) / _COMPONENT_Y_STEP) + 1)

    def _start_point(self, ladder_type: str) -> tuple[float, float]:
        start_x, start_y = self._ladder_mgr.get_insertion_point(ladder_type)
        if start_x == 0.0 and start_y == 0.0:
            return _DEFAULT_START_X, _DEFAULT_START_Y
        return start_x, start_y

    def count_pages(self, io_items: Iterable[IOItem]) -> int:
        """How many L pages `generate()` would emit, without drawing anything."""
        available = set(self._ladder_mgr.list_templates())
        total = 0
        for ladder_type, components in group_by_ladder_type(io_items, self._type_map).items():
            if ladder_type not in available:
                continue
            _, start_y = self._start_point(ladder_type)
            per_page = self._components_per_page(ladder_type, start_y)
            total += -(-len(components) // per_page)
        return total

    # ── drawing ─────────────────────────────────────────────────────────────

    def generate(
        self,
        output_dir: Path,
        config: LadderConfig,
        io_items: list[IOItem],
        first_page: int = 1,
    ) -> tuple[list[Path], list[str]]:
        """Write the L pages for *io_items*; returns (files, errors)."""
        grouped = group_by_ladder_type(io_items, self._type_map)
        available = set(self._ladder_mgr.list_templates())

        generated: list[Path] = []
        errors: list[str] = []
        page = first_page

        for ladder_type, components in grouped.items():
            if ladder_type not in available:
                errors.append(f"Ladder template '{ladder_type}' not found; skipping.")
                continue

            start_x, start_y = self._start_point(ladder_type)
            per_page = self._components_per_page(ladder_type, start_y)
            cotag_counter = 100  # CR100, CR101, … unique per ladder type

            for chunk_start in range(0, len(components), per_page):
                chunk = components[chunk_start : chunk_start + per_page]
                page_str = f"L{page:03d}"
                dxf_path = output_dir / f"{page_str}.dxf"

                template_doc = self._ladder_mgr.load_template(ladder_type)
                placements: list[tuple[Any, float, float, IOItem]] = []
                for comp_idx, io_item in enumerate(chunk):
                    comp_name = self._component_map.get(io_item.io_type_name, "")
                    if not comp_name:
                        continue
                    comp_doc = self._component_mgr.load_template(comp_name)
                    if comp_doc is None:
                        continue
                    comp_doc = self._prepare_component(comp_doc, io_item, cotag_counter, page)
                    cotag_counter += 1
                    ip_x, ip_y = self._component_mgr.get_insertion_point(comp_name)
                    off_x, off_y = self._component_mgr.get_offset(comp_name)
                    placements.append(
                        (
                            comp_doc,
                            start_x - ip_x + off_x,
                            start_y - ip_y + off_y - comp_idx * _COMPONENT_Y_STEP,
                            io_item,
                        )
                    )

                page_config = dataclasses.replace(config, drawing_number=page_str)
                ok, message = DrawingGenerator(page_config).generate(
                    [],
                    str(dxf_path),
                    template_doc,
                    io_items=io_items,
                    io_template_placements=placements or None,
                    controller_number=io_items[0].number if io_items else 0,
                    controller_prefix=self.machine_prefix,
                    control=False,
                )
                if ok:
                    generated.append(dxf_path)
                else:
                    errors.append(f"{page_str}: {message}")
                page += 1

        return generated, errors

    # ── placeholder substitution ────────────────────────────────────────────

    def _prepare_component(self, source_doc, io_item: IOItem, comp_number: int, ctrl_num: int):
        """Copy *source_doc* with its attribute placeholders resolved."""
        buffer = _io.StringIO()
        source_doc.write(buffer)
        buffer.seek(0)
        copy = ezdxf.read(buffer)

        prefix = self.machine_prefix
        tag = io_item.tag.upper() if io_item.tag else ""
        io_dir = "I" if (io_item.io_type or "").lower() == "input" else "O"
        address = io_item.address.upper() if io_item.address else ""
        if not address:
            signal = io_item.signal_type[0].upper() if io_item.signal_type else "D"
            address = f"{signal}{io_dir}{comp_number}"
        address = f"{prefix}-{ctrl_num}-{address}"

        substitutions = {
            "COTAG": f"CR{comp_number}",
            "CONTL-IO": f"{io_item.number}",
            "NAME": tag,
            "COM_NAME": f"COM_{tag}",
            "%tagstrip%": f"{prefix}{io_dir}-{ctrl_num}",
            "%tagcom%": f"{prefix}{io_dir}-{ctrl_num}",
            "COM_CONTL": f"COM_{address}",
            "NUM": f"{address}",
            "COM_NUM": f"COM_{io_item.number}",
            "CIRCUIT#": f"CIRCUIT{io_item.circuit_no}" if io_item.circuit_no else "CIRCUIT#",
            "POS": address,
            "PS#": f"PS{self.ps_count}",
            "FULL_NAME": io_item.description,
            "SOL#": f"SOL{self.solcount}",
            "SD#": f"SD{self.sdcount}",
        }

        for entity in copy.modelspace():
            if entity.dxftype() != "INSERT":
                continue
            try:
                for attrib in entity.attribs:
                    text = attrib.dxf.get("text", "")
                    if text == "PS#":
                        self.ps_count += 1
                    elif text == "SOL#":
                        self.solcount += 1
                    elif text == "SD#":
                        self.sdcount += 1
                    if text in substitutions:
                        attrib.dxf.text = substitutions[text]
                    elif text == f"%{io_item.tag}%":
                        attrib.dxf.text = f"{prefix}{io_dir}-{ctrl_num}"
                    elif text == f"%COM_{io_item.tag}%":
                        attrib.dxf.text = f"COM_{prefix}{io_dir}-{ctrl_num}"
            except Exception:
                pass

        return copy
