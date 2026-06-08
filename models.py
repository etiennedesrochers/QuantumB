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


@dataclass
class Valve:
    """A valve instance belonging to a circuit."""
    tag: str         # unique tag / reference, e.g. "V001"
    valve_type: str  # one of the configured valve types
    description: str = ""
    circuit_name: str = ""   # name of the owning Circuit (for cross-reference)


@dataclass
class Circuit:
    """A named circuit that references an ordered list of templates."""
    name: str
    circuit_number: str
    description: str
    templates: list[str] = field(default_factory=list)   # template names, may repeat
    valves: list = field(default_factory=list)            # list[Valve]

    def __post_init__(self):
        # Convert plain dicts (from JSON deserialization) to Valve objects
        self.valves = [
            Valve(**v) if isinstance(v, dict) else v
            for v in self.valves
        ]
