"""
XNNOV Selection Tool Adapter

Converts XNNOV Selection Tool JSON (circuits + drawing pages) into 
dummy QuantumB project structure (.aepj format).

JSON Input Schema:
{
  "project_name": "...",
  "project_number": "...",
  "revision": "A",
  "drawn_by": "...",
  "circuits": [
    {
      "name": "CU001",
      "description": "...",
      "pages": ["p1.dxf", "p2.dxf", ...]
    },
    ...
  ]
}

Output: Dictionary compatible with project_manager.save_project()
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Optional
from dataclasses import dataclass, field

from .models import Circuit, Template


@dataclass
class SelectionData:
    """Parsed XNNOV Selection Tool JSON data."""
    project_name: str
    project_number: str = ""
    revision: str = "A"
    drawn_by: str = ""
    circuits: list[dict] = field(default_factory=list)


def load_selection_json(json_path: str) -> tuple[bool, str, Optional[SelectionData]]:
    """
    Load and parse XNNOV Selection Tool JSON file.
    
    Parameters
    ----------
    json_path : str
        Path to the .json file from Selection Tool
    
    Returns
    -------
    tuple[bool, str, Optional[SelectionData]]
        (success, message, data)
    """
    try:
        with open(json_path, 'r', encoding='utf-8') as f:
            raw = json.load(f)
        
        data = SelectionData(
            project_name=raw.get("project_name", "XNNOV Project"),
            project_number=raw.get("project_number", ""),
            revision=raw.get("revision", "A"),
            drawn_by=raw.get("drawn_by", ""),
            circuits=raw.get("circuits", [])
        )
        
        if not data.circuits:
            return False, "No circuits found in selection data", None
        
        return True, "Selection data loaded successfully", data
    
    except FileNotFoundError:
        return False, f"Selection file not found: {json_path}", None
    except json.JSONDecodeError as e:
        return False, f"Invalid JSON: {e}", None
    except Exception as e:
        return False, f"Error loading selection data: {e}", None


def create_dummy_circuit(
    circuit_name: str,
    circuit_description: str,
    compressors: list[dict]
) -> Circuit:
    """
    Create a dummy Circuit object from XNNOV selection data.
    
    Parameters
    ----------
    circuit_name : str
        Circuit identifier (e.g., "CU001")
    circuit_description : str
        Human-readable description
    compressors : list[dict]
        List of compressor definitions, each with model_number, description, and templates
        Example: [
            {
                "model_number": "COMP-001",
                "description": "First Compressor",
                "templates": [
                    {"name": "p1.dxf", "quantity": 1},
                    {"name": "p2.dxf", "quantity": 2}
                ]
            },
            ...
        ]
    
    Returns
    -------
    Circuit
        Dummy circuit with templates flattened and populated from compressors
    """
    # Flatten compressors into a single templates list
    # For each template with quantity N, add it N times
    templates = []
    
    for compressor in compressors:
        template_list = compressor.get("templates", [])
        for template_def in template_list:
            template_name = template_def.get("name", "")
            quantity = template_def.get("quantity", 1)
            
            # Add template N times based on quantity
            for idx in range(quantity):
                template_obj = Template(
                    name=template_name,
                    ladder_type="io" if "io" in template_name.lower() else "ladder",
                    part_of_ladder=len(templates) + 1,
                    height=0.0
                )
                templates.append(template_obj)
    
    # Create minimal dummy circuit
    circuit = Circuit(
        name=circuit_name,
        circuit_number=circuit_name,
        description=circuit_description,
        templates=templates,
        valves=[],
        circuit_ios=[]
    )
    
    return circuit


def adapt_selection_to_project(
    selection_data: SelectionData
) -> tuple[bool, str, Optional[dict]]:
    """
    Convert XNNOV Selection Tool data to .aepj project structure.
    
    Parameters
    ----------
    selection_data : SelectionData
        Parsed selection JSON
    
    Returns
    -------
    tuple[bool, str, Optional[dict]]
        (success, message, project_dict)
        
        project_dict keys:
        - settings: dict with title, project, drawing_number, revision, drawn_by, paper_size
        - project_circuits: list[str] (circuit names)
        - io_items: list (empty for dummy circuits)
        - rungs: list (empty for dummy circuits)
    """
    try:
        # Build settings from selection data
        settings = {
            "title": "ELECTRICAL DRAWING",
            "project": selection_data.project_name,
            "drawing_number": selection_data.project_number,
            "revision": selection_data.revision,
            "drawn_by": selection_data.drawn_by,
            "paper_size": "A3 Landscape"
        }
        
        # Extract circuit names for project_circuits list
        project_circuits = []
        for circuit_data in selection_data.circuits:
            project_circuits.append(circuit_data.get("name", ""))
        
        # Minimal I/O items and rungs (empty)
        io_items = []
        rungs = []
        
        project_dict = {
            "settings": settings,
            "project_circuits": project_circuits,
            "io_items": io_items,
            "rungs": rungs
        }
        
        return True, "Selection data adapted to project format", project_dict
    
    except Exception as e:
        return False, f"Error adapting selection data: {e}", None


def get_dummy_circuits_from_selection(
    selection_data: SelectionData
) -> tuple[bool, str, list[Circuit]]:
    """
    Generate dummy Circuit objects from selection data.
    
    These circuits can be used to populate the circuit library
    or to override the library lookup in CLIGenerator.
    
    Handles both old format (pages) and new format (compressors with templates).
    
    Parameters
    ----------
    selection_data : SelectionData
        Parsed selection JSON
    
    Returns
    -------
    tuple[bool, str, list[Circuit]]
        (success, message, circuits)
    """
    try:
        circuits = []
        for circuit_data in selection_data.circuits:
            circuit_name = circuit_data.get("name", "")
            circuit_desc = circuit_data.get("description", "")
            
            # Support both old format (pages) and new format (compressors)
            if "compressors" in circuit_data:
                # New format: compressors with templates
                compressors = circuit_data.get("compressors", [])
                circuit = create_dummy_circuit(
                    circuit_name=circuit_name,
                    circuit_description=circuit_desc,
                    compressors=compressors
                )
            elif "pages" in circuit_data:
                # Legacy format: direct pages list
                # Convert old format to compressor format for backward compatibility
                pages = circuit_data.get("pages", [])
                legacy_compressors = [
                    {
                        "model_number": "LEGACY",
                        "description": circuit_desc,
                        "templates": [{"name": p, "quantity": 1} for p in pages]
                    }
                ]
                circuit = create_dummy_circuit(
                    circuit_name=circuit_name,
                    circuit_description=circuit_desc,
                    compressors=legacy_compressors
                )
            else:
                # Empty circuit
                circuit = Circuit(
                    name=circuit_name,
                    circuit_number=circuit_name,
                    description=circuit_desc,
                    templates=[],
                    valves=[],
                    circuit_ios=[]
                )
            
            circuits.append(circuit)
        
        return True, f"Created {len(circuits)} dummy circuit(s)", circuits
    
    except Exception as e:
        return False, f"Error creating dummy circuits: {e}", []


# Full workflow function
def generate_from_selection(
    json_path: str
) -> tuple[bool, str, Optional[dict], Optional[list[Circuit]]]:
    """
    Complete workflow: Load selection JSON → create project + dummy circuits.
    
    Parameters
    ----------
    json_path : str
        Path to XNNOV Selection Tool JSON file
    
    Returns
    -------
    tuple[bool, str, Optional[dict], Optional[list[Circuit]]]
        (success, message, project_dict, circuits)
    """
    # Step 1: Load selection JSON
    success, msg, selection_data = load_selection_json(json_path)
    if not success:
        return False, msg, None, None
    
    # Step 2: Adapt to project format
    success, msg, project_dict = adapt_selection_to_project(selection_data)
    if not success:
        return False, msg, None, None
    
    # Step 3: Create dummy circuits
    success, msg, circuits = get_dummy_circuits_from_selection(selection_data)
    if not success:
        return False, msg, None, None
    
    return True, "Selection data successfully converted to project + circuits", project_dict, circuits
