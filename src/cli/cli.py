"""
Command-line interface for the AutoCAD Electrical Drawing Generator.
Allows non-interactive generation from project files with parameters.

Usage:
    python app.py --project <project_file> --output <output_folder> [--format {dxf|dwg|both}]
    
Example:
    python app.py --project my_project.aepj --output ./output --format both
"""
from __future__ import annotations

import argparse
import sys
import math
import dataclasses
import re
from pathlib import Path
from typing import Optional

import src.core.project_manager as pm
import src.core.circuit_library as cl
import src.core.module_manager as mm
import src.core.selection_adapter as sa
from src.core.drawing_generator import DrawingGenerator, LadderConfig, Rung, Component
from src.core.io_manager import IOItem
from src.core.models import Circuit, Valve, Template
from src.core.template_manager import (
    TemplateManager,
    CTRL_TEMPLATES_DIR,
    IO_TEMPLATES_DIR,
    LADDER_TEMPLATES_DIR,
    VALVES_TEMPLATES_DIR,
    _find_oda_converter,
    convert_folder_dxf_to_dwg,
)


# ─────────────────────────────────────────────────────────────────────────────
# Conversion helpers
# ─────────────────────────────────────────────────────────────────────────────

def _dict_to_io_item(data: dict) -> IOItem:
    """Convert a dictionary to an IOItem dataclass instance."""
    return IOItem(
        tag=data.get("tag", ""),
        io_type=data.get("io_type", "Input"),
        address=data.get("address", ""),
        description=data.get("description", ""),
        panel=data.get("panel", ""),
        signal_type=data.get("signal_type", ""),
        io_type_name=data.get("io_type_name", ""),
        terminal=data.get("terminal", ""),
        cable=data.get("cable", ""),
        notes=data.get("notes", ""),
        old_name=data.get("old_name", ""),
        old_description=data.get("old_description", ""),
        number=data.get("number", ""),
    )


def _dict_to_component(data: dict) -> Component:
    """Convert a dictionary to a Component dataclass instance."""
    return Component(
        symbol=data.get("symbol", ""),
        tag=data.get("tag", ""),
        description=data.get("description", ""),
        io_tag=data.get("io_tag", ""),
        tag_source=data.get("tag_source", "manual"),
        description_source=data.get("description_source", "manual"),
    )


def _dict_to_rung(data: dict) -> Rung:
    """Convert a dictionary to a Rung dataclass instance."""
    components = []
    for comp_data in data.get("components", []):
        components.append(_dict_to_component(comp_data))
    
    return Rung(
        components=components,
        rung_number=data.get("rung_number", 0),
        description=data.get("description", ""),
    )


def _convert_io_items(items_data: list) -> list[IOItem]:
    """Convert a list of IO item dictionaries to IOItem instances."""
    if not items_data:
        return []
    
    result = []
    for item_data in items_data:
        if isinstance(item_data, IOItem):
            # Already an IOItem instance
            result.append(item_data)
        elif isinstance(item_data, dict):
            # Convert dict to IOItem
            result.append(_dict_to_io_item(item_data))
        else:
            # Skip invalid entries
            pass
    return result


def _convert_rungs(rungs_data: list) -> list[Rung]:
    """Convert a list of rung dictionaries to Rung instances."""
    if not rungs_data:
        return []
    
    result = []
    for rung_data in rungs_data:
        if isinstance(rung_data, Rung):
            # Already a Rung instance
            result.append(rung_data)
        elif isinstance(rung_data, dict):
            # Convert dict to Rung
            result.append(_dict_to_rung(rung_data))
        else:
            # Skip invalid entries
            pass
    return result


def _normalize_io_type_name(value: str) -> str:
    """Normalize IO type names for robust matching across formats."""
    if not value:
        return ""
    text = value.strip().lower()
    text = re.sub(r"[^a-z0-9]+", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _resolve_io_type_def(io_item: IOItem, io_type_map: dict, fallback_direction: str) -> dict:
    """Resolve an IO type definition using exact name, normalized alias, or direction fallback."""
    if not io_item:
        return {}

    exact = io_type_map.get(io_item.io_type_name, {})
    if exact:
        return exact

    normalized_name = _normalize_io_type_name(io_item.io_type_name)
    if normalized_name:
        for defn in io_type_map.values():
            if _normalize_io_type_name(defn.get("name", "")) == normalized_name:
                return defn

    direction = (io_item.io_type or fallback_direction or "").strip().lower()
    if direction == "output":
        for defn in io_type_map.values():
            if (defn.get("direction") or "").strip().lower() == "output":
                return defn
    elif direction == "input":
        for defn in io_type_map.values():
            if (defn.get("direction") or "").strip().lower() == "input":
                return defn

    return {}


def _get_io_template_name(
    io_item: IOItem,
    io_type_map: dict,
    slot_idx: int,
    fallback_direction: str,
    input_common_shared: bool = False,
    shared_input_index: int | None = None,
) -> str:
    """Return the correct template name for an IO slot, including shared-common pairs."""
    io_type_def = _resolve_io_type_def(io_item, io_type_map, fallback_direction)
    shared_slot_index = shared_input_index if shared_input_index is not None else slot_idx
    if (
        input_common_shared
        and (fallback_direction or "").strip().lower() == "input"
        and io_type_def.get("shared", False)
        and ((shared_slot_index + 1) % 2 == 0)
    ):
        return io_type_def.get("shared_template", "") or io_type_def.get("io_template", "")
    return io_type_def.get("io_template", "")


def _get_output_slots(module_def: dict) -> list[dict]:
    """Return controller output slot coordinates, preferring output_commons when present."""
    if not module_def:
        return []
    output_commons = module_def.get("output_commons", [])
    if output_commons:
        return output_commons
    return module_def.get("outputs", [])


class CLIGenerator:
    """Handles non-interactive drawing generation from project files."""

    def __init__(self, project_path: str, output_dir: str, output_format: str = "dxf", dummy_circuits: list[Circuit] = None):
        """
        Initialize the CLI generator.

        Parameters
        ----------
        project_path : str
            Path to the .aepj project file
        output_dir : str
            Directory where generated files will be saved
        output_format : str
            Output format: "dxf", "dwg", or "both" (default: "dxf")
        dummy_circuits : list[Circuit], optional
            List of dummy circuits from selection adapter (overrides library lookup)
        """
        self.project_path = Path(project_path)
        self.output_dir = Path(output_dir)
        self.output_format = output_format.lower()
        self.dummy_circuits = dummy_circuits or []
        
        # Validate project file exists
        if not self.project_path.exists():
            raise FileNotFoundError(f"Project file not found: {self.project_path}")
        
        # Create output directory
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # Initialize template managers
        self.template_mgr = TemplateManager(LADDER_TEMPLATES_DIR)
        self.ctrl_template_mgr = TemplateManager(CTRL_TEMPLATES_DIR)
        self.io_template_mgr = TemplateManager(IO_TEMPLATES_DIR)
        
        # Load libraries - convert to proper objects
        circuit_dicts = cl.load_library()
        self.circuits = [Circuit(**d) for d in circuit_dicts]
        
        # Add dummy circuits to the list (they take precedence in lookup)
        self.circuits.extend(self.dummy_circuits)
        
        self.modules = mm.load_modules()
        self.io_types = self._load_io_types()

    def _load_io_types(self) -> list[dict]:
        """Load IO types from the library."""
        try:
            import json
            io_types_path = Path(__file__).resolve().parent.parent.parent / "config" / "io_types_library.json"
            if io_types_path.exists():
                with open(io_types_path, 'r', encoding='utf-8') as f:
                    return json.load(f) or []
        except Exception as e:
            print(f"Warning: Could not load IO types: {e}", file=sys.stderr)
        return []

    def _lookup_circuit(self, name: str) -> Optional[Circuit]:
        """Look up a circuit by name in the global library."""
        for circuit in self.circuits:
            if circuit.name == name:
                return circuit
        return None

    def _build_config(self, settings: dict) -> LadderConfig:
        """Build LadderConfig from project settings."""
        paper_sizes = {
            "A4 Portrait": (210, 297),
            "A4 Landscape": (297, 210),
            "A3 Portrait": (297, 420),
            "A3 Landscape": (420, 297),
        }
        
        paper_size = settings.get("paper_size", "A3 Landscape")
        width, height = paper_sizes.get(paper_size, (420, 297))
        
        return LadderConfig(
            title=settings.get("title", "ELECTRICAL DRAWING"),
            project=settings.get("project", ""),
            drawing_number=settings.get("drawing_number", "001"),
            revision=settings.get("revision", "A"),
            drawn_by=settings.get("drawn_by", ""),
            paper_width=width,
            paper_height=height,
        )

    def _apply_generation_substitutions(
        self,
        rungs: list[Rung],
        io_items: list[IOItem],
        config: LadderConfig,
    ) -> tuple[list[Rung], list[IOItem], LadderConfig]:
        """
        Apply any necessary substitutions before generation.
        This is a placeholder for any preprocessing logic.
        """
        # For now, return as-is
        return rungs, io_items, config

    def _build_generation_io_items(
        self,
        project_circuits: list[str],
        manual_io_items: list[IOItem] | None = None,
    ) -> list[IOItem]:
        """Build the IO list used for generation from circuits and templates.

        This mirrors the GUI workflow: circuit-level I/O definitions are added
        first, then template-derived I/O from each circuit template is appended.
        Manual IO items are added last if they are not already represented.
        """
        manual_ios = list(manual_io_items or [])
        built_items: list[IOItem] = []

        for circuit_name in project_circuits:
            circuit = self._lookup_circuit(circuit_name)
            if circuit is None:
                continue

            circuit_no = circuit.circuit_number or circuit_name

            for io_entry in circuit.circuit_ios:
                if not isinstance(io_entry, dict):
                    continue
                io_old_name = io_entry.get("name", "")
                io_old_desc = io_entry.get("description", "")
                io_name = str(io_entry.get("name", "")).replace("#", circuit_no)
                io_desc = str(io_entry.get("description", "")).replace("#", circuit_no)
                built_items.append(
                    IOItem(
                        tag=io_name,
                        io_type=io_entry.get("direction", "Input"),
                        description=io_desc,
                        signal_type=io_entry.get("signal_type", ""),
                        signal_category=io_entry.get("signal_type", ""),
                        io_type_name=io_entry.get("io_type", ""),
                        old_name=io_old_name,
                        old_description=io_old_desc,
                        circuit_name=circuit_name,
                        circuit_no=circuit_no,
                        template_name="",
                    )
                )

            for template_entry in circuit.templates:
                tmpl_name = template_entry.name if isinstance(template_entry, Template) else str(template_entry)
                if not tmpl_name:
                    continue
                for io_entry in self.template_mgr.get_template_ios(tmpl_name):
                    if not isinstance(io_entry, dict):
                        continue
                    io_old_name = io_entry.get("name", "")
                    io_old_desc = io_entry.get("description", "")
                    io_name = str(io_entry.get("name", "")).replace("#", circuit_no)
                    io_desc = str(io_entry.get("description", "")).replace("#", circuit_no)
                    built_items.append(
                        IOItem(
                            tag=io_name,
                            io_type=io_entry.get("direction", "Input"),
                            description=io_desc,
                            signal_type=io_entry.get("signal_type", ""),
                            signal_category=io_entry.get("signal_category", ""),
                            io_type_name=io_entry.get("io_type", ""),
                            old_name=io_old_name,
                            old_description=io_old_desc,
                            circuit_name=circuit_name,
                            circuit_no=circuit_no,
                            template_name=tmpl_name,
                        )
                    )

        existing_keys = {
            (item.tag, item.io_type, item.circuit_name, item.circuit_no, item.template_name)
            for item in built_items
        }
        for manual_io in manual_ios:
            key = (
                manual_io.tag,
                manual_io.io_type,
                manual_io.circuit_name,
                manual_io.circuit_no,
                manual_io.template_name,
            )
            if key not in existing_keys:
                built_items.append(manual_io)
                existing_keys.add(key)

        return built_items

    def _enrich_io_item(
        self,
        io_item: IOItem,
        ctrl_idx: int,
        slot_idx: int,
        io_direction: str,
    ) -> IOItem:
        """Enrich an IO item with controller and slot information."""
        # Create a modified copy of the IO item with additional context
        enriched = dataclasses.replace(io_item)
        return enriched

    def generate(self) -> tuple[bool, str]:
        """
        Generate drawings from the project file.

        Returns
        -------
        tuple[bool, str]
            (success, message)
        """
        try:
            # Load project
            print(f"Loading project: {self.project_path}")
            success, message, project_data = pm.load_project(str(self.project_path))
            if not success:
                return False, f"Failed to load project: {message}"
            
            # Extract data from project
            settings = project_data.get("settings", {})
            project_circuits = project_data.get("project_circuits", [])
            io_items_raw = project_data.get("io_items", [])
            rungs_raw = project_data.get("rungs", [])
            
            # Convert dictionaries to dataclass instances
            io_items = _convert_io_items(io_items_raw)
            rungs = _convert_rungs(rungs_raw)

            # Build generation IO items from project circuits/templates, mirroring the GUI.
            generated_io_items = self._build_generation_io_items(project_circuits, io_items)
            if generated_io_items:
                io_items = generated_io_items
            
            # Validate project has circuits
            if not project_circuits:
                return False, "Project has no circuits defined"
            
            print(f"Found {len(project_circuits)} circuit(s)")
            print(f"Found {len(io_items)} I/O item(s)")
            print(f"Found {len(rungs)} rung(s)")
            
            # Build config and apply substitutions
            config = self._build_config(settings)
            rungs, io_items, config = self._apply_generation_substitutions(
                rungs, io_items, config
            )
            
            # Determine if DWG conversion is available
            oda_available = _find_oda_converter() is not None
            use_dwg = oda_available and self.output_format in ("dwg", "both")
            
            generated_files: list[Path] = []
            errors: list[str] = []
            page = 1
            
            # Generate circuit pages
            print("\n=== Generating Circuit Pages ===")
            for circuit_name in project_circuits:
                circuit = self._lookup_circuit(circuit_name)
                if circuit is None:
                    print(f"Warning: Circuit '{circuit_name}' not found in library")
                    continue
                
                templates = circuit.templates if circuit.templates else []
                for t in templates:
                    tmpl_name = t.name if isinstance(t, Template) else t
                    page_str = f"E{page:03d}"
                    dxf_path = self.output_dir / f"{page_str}.dxf"
                    
                    print(f"  Generating {page_str}: {tmpl_name}...", end=" ")
                    
                    template_doc = self.template_mgr.load_template(tmpl_name) if tmpl_name else None
                    page_config = dataclasses.replace(config, drawing_number="0")
                    gen = DrawingGenerator(page_config)
                    
                    ok, msg = gen.generate(
                        rungs, str(dxf_path), template_doc, io_items=io_items, controller_number=0
                    )
                    if ok:
                        generated_files.append(dxf_path)
                        print("[OK]")
                    else:
                        errors.append(f"{page_str}: {msg}")
                        print(f"[ERROR] ({msg})")
                    
                    page += 1
            
            # Generate controller pages (if modules are available)
            if self.modules and io_items:
                print("\n=== Generating Controller Pages ===")
                
                # Find the first module definition (or use a default)
                module_def = self.modules[0] if self.modules else None
                
                if module_def:
                    mod_inputs = len(module_def.get("inputs", []))
                    mod_outputs = len(module_def.get("outputs", []))
                    total_inputs = sum(1 for io in io_items if io.io_type == "Input")
                    total_outputs = sum(1 for io in io_items if io.io_type == "Output")
                    
                    num_ctrl = 1
                    if mod_inputs > 0 and total_inputs > 0:
                        num_ctrl = max(num_ctrl, math.ceil(total_inputs / mod_inputs))
                    if mod_outputs > 0 and total_outputs > 0:
                        num_ctrl = max(num_ctrl, math.ceil(total_outputs / mod_outputs))
                    
                    ctrl_tmpl_name = module_def.get("template", "")
                    io_type_map = {t["name"]: t for t in self.io_types}
                    
                    input_ios = [io for io in io_items if io.io_type == "Input"]
                    output_ios = [io for io in io_items if io.io_type == "Output"]
                    mod_input_slots = module_def.get("inputs", [])
                    mod_output_slots = _get_output_slots(module_def)
                    
                    for ctrl_idx in range(1, num_ctrl + 1):
                        page_str = f"C{ctrl_idx:03d}"
                        dxf_path = self.output_dir / f"{page_str}.dxf"
                        
                        print(f"  Generating {page_str}: {module_def.get('name', 'Module')}...", end=" ")
                        
                        ctrl_tmpl_doc = (
                            self.ctrl_template_mgr.load_template(ctrl_tmpl_name)
                            if ctrl_tmpl_name else None
                        )
                        
                        # Build IO template placements
                        io_template_placements: list = []
                        
                        # Inputs for this page
                        start_in = (ctrl_idx - 1) * mod_inputs
                        page_inputs = input_ios[start_in : start_in + mod_inputs]
                        input_common_shared = module_def.get("input_common_shared", False)
                        shared_input_index = 0
                        for slot_idx, io_item in enumerate(page_inputs):
                            io_type_def = _resolve_io_type_def(io_item, io_type_map, "Input")
                            tmpl_name = _get_io_template_name(
                                io_item,
                                io_type_map,
                                slot_idx,
                                "Input",
                                input_common_shared=input_common_shared,
                                shared_input_index=shared_input_index,
                            )
                            if not tmpl_name or slot_idx >= len(mod_input_slots):
                                continue
                            tmpl_doc = self.io_template_mgr.load_template(tmpl_name)
                            if tmpl_doc is None:
                                continue
                            slot = mod_input_slots[slot_idx]
                            ip_x, ip_y = self.io_template_mgr.get_insertion_point(tmpl_name)
                            enriched = self._enrich_io_item(io_item, ctrl_idx, slot_idx, "Input")
                            io_template_placements.append(
                                (tmpl_doc, slot["x"] - ip_x, slot["y"] - ip_y, enriched)
                            )
                            if input_common_shared and io_type_def.get("shared", False):
                                shared_input_index += 1
                        
                        # Outputs for this page
                        start_out = (ctrl_idx - 1) * mod_outputs
                        page_outputs = output_ios[start_out : start_out + mod_outputs]
                        for slot_idx, io_item in enumerate(page_outputs):
                            io_type_def = _resolve_io_type_def(io_item, io_type_map, "Output")
                            tmpl_name = io_type_def.get("io_template", "")
                            if not tmpl_name or slot_idx >= len(mod_output_slots):
                                continue
                            tmpl_doc = self.io_template_mgr.load_template(tmpl_name)
                            if tmpl_doc is None:
                                continue
                            slot = mod_output_slots[slot_idx]
                            ip_x, ip_y = self.io_template_mgr.get_insertion_point(tmpl_name)
                            enriched = self._enrich_io_item(io_item, ctrl_idx, slot_idx, "Output")
                            io_template_placements.append(
                                (tmpl_doc, slot["x"] - ip_x, slot["y"] - ip_y, enriched)
                            )
                        
                        page_config = dataclasses.replace(config, drawing_number=page_str)
                        gen = DrawingGenerator(page_config)
                        
                        ok, msg = gen.generate(
                            [], str(dxf_path), ctrl_tmpl_doc,
                            io_items=io_items,
                            io_template_placements=io_template_placements or None,
                        )
                        if ok:
                            generated_files.append(dxf_path)
                            print("[OK]")
                        else:
                            errors.append(f"{page_str}: {msg}")
                            print(f"[ERROR] ({msg})")
            
            # Convert DXF to DWG if requested and available
            if use_dwg and generated_files:
                print("\n=== Converting DXF to DWG ===")
                print("Converting files...", end=" ")
                converted, total_dxf, conv_error = convert_folder_dxf_to_dwg(str(self.output_dir))
                if conv_error:
                    errors.append(f"DWG conversion: {conv_error}")
                    print(f"[ERROR] ({conv_error})")
                else:
                    print(f"[OK] ({converted} file(s) converted)")
            
            # Summary
            print("\n=== Generation Summary ===")
            if self.output_format == "dwg":
                ext = "DWG"
            elif self.output_format == "both":
                ext = "DXF/DWG"
            else:
                ext = "DXF"
            
            summary = f"[OK] Generated {len(generated_files)} {ext} file(s) to:\n  {self.output_dir}"
            
            if errors:
                summary += f"\n\n[WARNING] {len(errors)} error(s) occurred:"
                for err in errors:
                    summary += f"\n  - {err}"
                print(summary)
                return False, summary
            else:
                print(summary)
                return True, summary

        except Exception as exc:
            error_msg = f"Error during generation: {exc}"
            print(f"[ERROR] {error_msg}", file=sys.stderr)
            import traceback
            traceback.print_exc()
            return False, error_msg


def main():
    """Parse command-line arguments and execute generation."""
    parser = argparse.ArgumentParser(
        description="AutoCAD Electrical Drawing Generator - CLI Mode",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Generate from .aepj project file (DXF, default)
  python app.py --project project.aepj --output ./output

  # Generate from XNNOV Selection Tool JSON
  python app.py --generate-from-selection selection.json --output ./output

  # Generate DWG files instead of DXF
  python app.py --project project.aepj --output ./output --format dwg

  # Generate both DXF and DWG
  python app.py --project project.aepj --output ./output --format both
        """,
    )
    
    # Make --project and --generate-from-selection mutually exclusive
    project_group = parser.add_mutually_exclusive_group(required=True)
    
    project_group.add_argument(
        "--project",
        help="Path to the project file (.aepj)",
    )
    
    project_group.add_argument(
        "--generate-from-selection",
        help="Path to XNNOV Selection Tool JSON file (generates dummy circuits and project)",
    )
    
    parser.add_argument(
        "--output",
        required=True,
        help="Output directory for generated files",
    )
    
    parser.add_argument(
        "--format",
        default="dxf",
        choices=["dxf", "dwg", "both"],
        help="Output format (default: dxf)",
    )
    
    args = parser.parse_args()
    
    try:
        print("=" * 60)
        print("AutoCAD Electrical Drawing Generator - CLI Mode")
        print("=" * 60)
        print()
        
        # Determine mode: project file or selection
        if args.generate_from_selection:
            # Selection Tool mode
            print(f"Loading XNNOV Selection Tool data from: {args.generate_from_selection}")
            success, message, project_dict, dummy_circuits = sa.generate_from_selection(
                args.generate_from_selection
            )
            
            if not success:
                print(f"[ERROR] Error: {message}", file=sys.stderr)
                return 1
            
            print(f"[OK] {message}")
            print(f"  Creating temporary project file with {len(dummy_circuits)} circuit(s)...")
            
            # Create temporary project file in output directory
            temp_project_path = Path(args.output) / "_temp_selection.aepj"
            temp_project_path.parent.mkdir(parents=True, exist_ok=True)
            
            success, save_msg = pm.save_project(
                str(temp_project_path),
                project_dict["settings"],
                project_dict["project_circuits"],
                project_dict["io_items"],
                project_dict["rungs"]
            )
            
            if not success:
                print(f"[ERROR] Error saving temporary project: {save_msg}", file=sys.stderr)
                return 1
            
            print(f"[OK] Temporary project created")
            
            # Generate from temporary project
            generator = CLIGenerator(str(temp_project_path), args.output, args.format, dummy_circuits=dummy_circuits)
        else:
            # Standard project file mode
            generator = CLIGenerator(args.project, args.output, args.format)
        
        success, message = generator.generate()
        
        print()
        return 0 if success else 1
        
    except Exception as exc:
        print(f"[ERROR] Fatal error: {exc}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
