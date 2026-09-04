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
    signal_category: str = ""  # "Analog" or "Digital"
    io_type_name: str = ""  # named IO type from io_types_library (e.g. "Status")
    terminal: str = ""
    cable: str = ""
    notes: str = ""
    old_name: str = ""       # original name from template (for reference)
    old_description: str = ""  # original description from template (for reference)
    number: str = ""         # number of the io in the list, used for generating the tagstrip and tagstrip_com
    circuit_name: str = ""   # circuit this IO belongs to
    circuit_no: str = ""     # circuit number
    template_name: str = ""  # template this IO came from

    def get_field(self, field_name: str) -> str:
        return getattr(self, field_name, "")
