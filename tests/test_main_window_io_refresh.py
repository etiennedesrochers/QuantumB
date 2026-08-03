from types import SimpleNamespace

from src.core.io_manager import IOItem
from src.gui.main_window import MainWindow


class _TableStub:
    def __init__(self) -> None:
        self.rows = 0

    def setRowCount(self, count: int) -> None:
        self.rows = count

    def rowCount(self) -> int:
        return self.rows

    def insertRow(self, _row: int) -> None:
        self.rows += 1

    def setItem(self, _row: int, _col: int, _item) -> None:
        pass


def test_refresh_io_table_preserves_project_loaded_manual_inputs():
    manual_input = IOItem(tag="Cool_En", io_type="Input", description="Cooling Enable")
    harness = SimpleNamespace(
        _io_table=_TableStub(),
        _io_items=[manual_input],
        _io_items_full=[],
        _io_table_row_mapping=[],
        _project_circuit_refs=[],
        _io_filter_type="All",
        _template_mgr=SimpleNamespace(get_template_ios=lambda _name: []),
        _resolve_project_circuit_numbers=lambda: [],
        _lookup_circuit=lambda _name: None,
        _apply_io_filter=lambda _filter: None,
        _refresh_io_summary=lambda: None,
    )

    MainWindow._refresh_io_table(harness)

    assert len(harness._io_items_full) == 1
    assert harness._io_items_full[0].tag == "Cool_En"
    assert harness._io_items_full[0].io_type == "Input"


def test_get_generation_io_items_includes_outputs_when_visible_list_is_filtered():
    input_io = IOItem(tag="DI_001", io_type="Input", description="Input")
    output_io = IOItem(tag="DO_001", io_type="Output", description="Output")

    harness = SimpleNamespace(
        _io_items=[input_io],  # Simulates UI filtered to Inputs only
        _io_items_full=[input_io, output_io],
        _sort_io_items=lambda items, _io_type: items,
    )

    generation_ios = MainWindow._get_generation_io_items(harness)

    assert len(generation_ios) == 2
    assert any(io.io_type == "Input" for io in generation_ios)
    assert any(io.io_type == "Output" for io in generation_ios)