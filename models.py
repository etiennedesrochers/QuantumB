"""
Data models shared across the application.
"""
from __future__ import annotations

from dataclasses import dataclass, field


# Built-in valve types; users can add custom ones via the valve type config.
DEFAULT_VALVE_TYPES: list[str] = ["heat", "cool", "reverse"]


@dataclass
class ValveIO:
    """A single I/O signal belonging to a valve type."""
    name: str
    description: str = ""
    signal_type: str = ""   # e.g. "24VDC", "4-20mA"
    direction: str = "Input"  # "Input" or "Output"
    io_type: str = ""
    controller: str = ""  # controller identifier/name this IO is connected to


@dataclass
class Valve:
    """A valve instance belonging to a circuit."""
    tag: str         # unique tag / reference, e.g. "V001"
    valve_type: str  # one of the configured valve types
    description: str = ""
    circuit_name: str = ""   # name of the owning Circuit (for cross-reference)


@dataclass
class Template:
    """A template with metadata for ladder diagram placement."""
    name: str                       # template file name (e.g., "E001", "controller_1")
    ladder_type: str = ""           # template type (e.g., "io", "controller", "ladder")
    part_of_ladder: str | int = ""  # which ladder/rung this template belongs to
    height: float = 0.0             # height of the ladder template


@dataclass
class Circuit:
    """A named circuit that references an ordered list of templates."""
    name: str
    circuit_number: str
    description: str
    templates: list[str | Template] = field(default_factory=list)   # template names or Template objects
    valves: list = field(default_factory=list)            # list[Valve]

    def __post_init__(self):
        # Convert plain dicts (from JSON deserialization) to Valve objects
        self.valves = [
            Valve(**v) if isinstance(v, dict) else v
            for v in self.valves
        ]
        
        # Convert template dicts to Template objects
        converted_templates = []
        for t in self.templates:
            if isinstance(t, dict):
                # If it has the new structure, create a Template object
                if 'name' in t and ('ladder_type' in t or 'part_of_ladder' in t):
                    converted_templates.append(Template(**t))
                # Otherwise it's a legacy template, keep as string
                elif 'name' in t:
                    converted_templates.append(t['name'])
                else:
                    # Assume it's a simple dict with just name key or it's a string key
                    converted_templates.append(t)
            else:
                # Keep strings and Template objects as-is
                converted_templates.append(t)
        self.templates = converted_templates

