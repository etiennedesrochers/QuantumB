import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.cli.cli import _get_io_template_name, _get_output_slots
from src.core.io_manager import IOItem


def test_shared_input_uses_shared_template_for_second_slot_when_module_shares_common():
    io_item = IOItem(tag="DI_002", io_type="Input", io_type_name="Status")
    io_type_map = {
        "Status": {
            "name": "Status",
            "direction": "Input",
            "shared": True,
            "io_template": "I_Status",
            "shared_template": "I_Status2",
        }
    }

    assert _get_io_template_name(io_item, io_type_map, 0, "Input", input_common_shared=True) == "I_Status"
    assert _get_io_template_name(io_item, io_type_map, 1, "Input", input_common_shared=True) == "I_Status2"


def test_shared_input_pairing_ignores_non_shared_slots_when_module_shares_common():
    shared_io = IOItem(tag="DI_002", io_type="Input", io_type_name="Status")
    io_type_map = {
        "Status": {
            "name": "Status",
            "direction": "Input",
            "shared": True,
            "io_template": "I_Status",
            "shared_template": "I_Status2",
        },
        "18v": {
            "name": "18v",
            "direction": "Input",
            "shared": False,
            "io_template": "in_18v",
            "shared_template": "",
        },
    }

    assert _get_io_template_name(shared_io, io_type_map, 1, "Input", input_common_shared=True, shared_input_index=0) == "I_Status"
    assert _get_io_template_name(shared_io, io_type_map, 3, "Input", input_common_shared=True, shared_input_index=1) == "I_Status2"


def test_output_slots_prefer_output_commons_when_present():
    module_def = {
        "outputs": [{"name": "Output 1", "x": 1.0, "y": 2.0}],
        "output_commons": [{"name": "COM_O_1", "x": 3.0, "y": 4.0}],
    }

    assert _get_output_slots(module_def) == module_def["output_commons"]
