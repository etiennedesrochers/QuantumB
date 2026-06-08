"""
I/O list data model and field definitions.
"""
from __future__ import annotations
from dataclasses import dataclass

IO_TYPES = ["Input", "Output"]

# Fields available on an IOItem that can be mapped to a Component display field
IO_FIELDS = ["tag", "address", "description", "panel", "signal_type", "terminal", "cable", "notes"]


@dataclass
class IOItem:
    tag: str                # reference / tag e.g. "DI_001"
    io_type: str = "Input"  # "Input" or "Output"
    address: str = ""       # PLC address e.g. "%I0.0"
    description: str = ""
    panel: str = ""
    signal_type: str = ""   # e.g. "24VDC", "4-20mA"
    terminal: str = ""
    cable: str = ""
    notes: str = ""

    def get_field(self, field_name: str) -> str:
        return getattr(self, field_name, "")
