"""
Dialog classes for the AutoCAD Electrical Drawing Generator UI.
"""
from __future__ import annotations

import json
from pathlib import Path

from PySide6.QtCore import Qt, QLocale
from PySide6.QtGui import QValidator
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QListWidget,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QSplitter,
    QSpinBox,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from drawing_generator import Rung, Component
from symbols.electrical_symbols import SYMBOL_REGISTRY
from models import Template



class CoordSpinBox(QDoubleSpinBox):
    """QDoubleSpinBox with 7 decimal places, dot as separator, and comma→dot auto-conversion."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setLocale(QLocale(QLocale.Language.English, QLocale.Country.UnitedStates))
        self.setDecimals(7)
        self.setRange(-999999.0, 999999.0)
        self.setMinimumWidth(130)

    def validate(self, text: str, pos: int):
        return super().validate(text.replace(",", "."), pos)

    def valueFromText(self, text: str) -> float:
        return super().valueFromText(text.replace(",", "."))
from io_manager import IO_TYPES, IO_FIELDS
from i18n import tr
from models import Circuit
from template_metadata_dialog import TemplateMetadataDialog


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _load_ladder_types() -> list[str]:
    """Load ladder types from ladder_types.json."""
    try:
        ladder_types_file = Path(__file__).parent / "ladder_types.json"
        with open(ladder_types_file, "r") as f:
            data = json.load(f)
            return data.get("ladder_types", [])
    except (FileNotFoundError, json.JSONDecodeError):
        return []

def _make_toolbar_row(*labels_callbacks: tuple[str, callable]) -> QWidget:
    """Return a widget containing a row of QPushButtons."""
    w = QWidget()
    lay = QHBoxLayout(w)
    lay.setContentsMargins(0, 0, 0, 0)
    for label, cb in labels_callbacks:
        btn = QPushButton(label)
        btn.clicked.connect(cb)
        lay.addWidget(btn)
    lay.addStretch()
    return w


# ---------------------------------------------------------------------------
# Component Dialog
# ---------------------------------------------------------------------------

class ComponentDialog(QDialog):
    """Add / edit a ladder component with optional I/O field linking."""

    _SOURCE_OPTIONS = ["manual"] + IO_FIELDS

    def __init__(self, parent=None, data: dict | None = None, io_items: list | None = None):
        super().__init__(parent)
        self.setWindowTitle(tr("dlg_component_title"))
        self.setMinimumWidth(480)
        self.result_data: dict | None = None
        self._io_items = io_items or []
        self._io_lookup = {item.tag: item for item in self._io_items}
        self._build(data)

    def _build(self, data: dict | None):
        layout = QVBoxLayout(self)
        form = QFormLayout()
        layout.addLayout(form)

        # Symbol
        self._sym_cb = QComboBox()
        self._sym_cb.addItems(list(SYMBOL_REGISTRY.keys()))
        form.addRow(tr("lbl_symbol_colon"), self._sym_cb)

        # Tag + source
        tag_row = QWidget()
        tag_lay = QHBoxLayout(tag_row)
        tag_lay.setContentsMargins(0, 0, 0, 0)
        self._tag_edit = QLineEdit()
        self._tag_src = QComboBox()
        self._tag_src.addItems(self._SOURCE_OPTIONS)
        tag_lay.addWidget(self._tag_edit, 3)
        tag_lay.addWidget(QLabel(tr("lbl_source")))
        tag_lay.addWidget(self._tag_src, 2)
        form.addRow(tr("lbl_tag_ref"), tag_row)

        # Description + source
        desc_row = QWidget()
        desc_lay = QHBoxLayout(desc_row)
        desc_lay.setContentsMargins(0, 0, 0, 0)
        self._desc_edit = QLineEdit()
        self._desc_src = QComboBox()
        self._desc_src.addItems(self._SOURCE_OPTIONS)
        desc_lay.addWidget(self._desc_edit, 3)
        desc_lay.addWidget(QLabel(tr("lbl_source")))
        desc_lay.addWidget(self._desc_src, 2)
        form.addRow(tr("col_description") + ":", desc_row)

        # I/O link group
        io_grp = QGroupBox(tr("grp_link_io"))
        io_lay = QFormLayout(io_grp)
        self._io_cb = QComboBox()
        self._io_cb.addItem("")
        for item in self._io_items:
            self._io_cb.addItem(item.tag)
        io_lay.addRow(tr("lbl_io_tag"), self._io_cb)
        self._io_info_lbl = QLabel()
        self._io_info_lbl.setStyleSheet("color: gray;")
        io_lay.addRow(self._io_info_lbl)
        layout.addWidget(io_grp)

        # Buttons
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self._ok)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        # Wire up signals
        self._io_cb.currentTextChanged.connect(self._on_io_selected)
        self._tag_src.currentTextChanged.connect(self._update_entry_states)
        self._desc_src.currentTextChanged.connect(self._update_entry_states)

        # Pre-fill
        if data:
            idx = self._sym_cb.findText(data.get("symbol", ""))
            if idx >= 0:
                self._sym_cb.setCurrentIndex(idx)
            self._tag_edit.setText(data.get("tag", ""))
            self._desc_edit.setText(data.get("description", ""))
            self._tag_src.setCurrentText(data.get("tag_source", "manual"))
            self._desc_src.setCurrentText(data.get("description_source", "manual"))
            io_tag = data.get("io_tag", "")
            if io_tag:
                self._io_cb.setCurrentText(io_tag)
                self._update_io_info(io_tag)

        self._update_entry_states()

    def _on_io_selected(self, io_tag: str):
        self._update_io_info(io_tag)
        if io_tag:
            if self._tag_src.currentText() == "manual":
                self._tag_src.setCurrentText("tag")
            if self._desc_src.currentText() == "manual":
                self._desc_src.setCurrentText("description")
        else:
            self._tag_src.setCurrentText("manual")
            self._desc_src.setCurrentText("manual")
        self._update_entry_states()

    def _update_io_info(self, io_tag: str):
        item = self._io_lookup.get(io_tag)
        if item:
            self._io_info_lbl.setText(
                f"[{item.io_type}]  Addr: {item.address}  Panel: {item.panel}  {item.description}"
            )
        else:
            self._io_info_lbl.setText("")

    def _update_entry_states(self):
        self._tag_edit.setEnabled(self._tag_src.currentText() == "manual")
        self._desc_edit.setEnabled(self._desc_src.currentText() == "manual")

    def _ok(self):
        self.result_data = {
            "symbol": self._sym_cb.currentText(),
            "tag": self._tag_edit.text().strip(),
            "description": self._desc_edit.text().strip(),
            "io_tag": self._io_cb.currentText(),
            "tag_source": self._tag_src.currentText(),
            "description_source": self._desc_src.currentText(),
        }
        self.accept()


# ---------------------------------------------------------------------------
# Rung Dialog
# ---------------------------------------------------------------------------

class RungDialog(QDialog):
    """Add / edit a ladder rung and its components."""

    def __init__(self, parent=None, rung: Rung | None = None, io_items: list | None = None):
        super().__init__(parent)
        self.setWindowTitle(tr("dlg_rung_title"))
        self.resize(700, 420)
        self.result_data: Rung | None = None
        self._io_items = io_items or []
        self._components: list[dict] = []
        self._build(rung)

    def _build(self, rung: Rung | None):
        layout = QVBoxLayout(self)

        # Rung info
        info_grp = QGroupBox(tr("grp_rung_info"))
        info_lay = QHBoxLayout(info_grp)
        info_lay.addWidget(QLabel(tr("lbl_rung_num")))
        self._num_edit = QLineEdit()
        self._num_edit.setFixedWidth(60)
        info_lay.addWidget(self._num_edit)
        info_lay.addSpacing(16)
        info_lay.addWidget(QLabel(tr("col_description") + ":"))
        self._desc_edit = QLineEdit()
        info_lay.addWidget(self._desc_edit, 1)
        layout.addWidget(info_grp)

        # Component table
        comp_grp = QGroupBox(tr("grp_components"))
        comp_lay = QVBoxLayout(comp_grp)
        _cols = [tr("col_symbol"), tr("col_tag"), tr("col_description"), tr("col_io_link")]
        self._table = QTableWidget(0, len(_cols))
        self._table.setHorizontalHeaderLabels(_cols)
        self._table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self._table.setSelectionBehavior(QTableWidget.SelectRows)
        self._table.setEditTriggers(QTableWidget.NoEditTriggers)
        self._table.doubleClicked.connect(self._edit_component)
        comp_lay.addWidget(self._table)
        comp_lay.addWidget(_make_toolbar_row(
            (tr("btn_add_component"), self._add_component),
            (tr("btn_edit_component"), self._edit_component),
            (tr("btn_remove"),         self._remove_component),
            (tr("btn_move_up"),        self._move_up),
            (tr("btn_move_down"),      self._move_down),
        ))
        layout.addWidget(comp_grp)

        # OK / Cancel
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self._ok)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        # Pre-fill
        if rung:
            self._num_edit.setText(str(rung.rung_number) if rung.rung_number else "")
            self._desc_edit.setText(rung.description)
            for comp in rung.components:
                self._components.append({
                    "symbol": comp.symbol, "tag": comp.tag,
                    "description": comp.description, "io_tag": comp.io_tag,
                    "tag_source": comp.tag_source,
                    "description_source": comp.description_source,
                })
            self._refresh_table()

    def _refresh_table(self):
        self._table.setRowCount(0)
        for c in self._components:
            row = self._table.rowCount()
            self._table.insertRow(row)
            for col, key in enumerate(("symbol", "tag", "description", "io_tag")):
                self._table.setItem(row, col, QTableWidgetItem(c.get(key, "")))

    def _selected_row(self) -> int:
        return self._table.currentRow() if self._table.selectedItems() else -1

    def _add_component(self):
        dlg = ComponentDialog(self, io_items=self._io_items)
        if dlg.exec() == QDialog.Accepted and dlg.result_data:
            self._components.append(dlg.result_data)
            self._refresh_table()

    def _edit_component(self):
        idx = self._selected_row()
        if idx < 0:
            return
        dlg = ComponentDialog(self, self._components[idx], io_items=self._io_items)
        if dlg.exec() == QDialog.Accepted and dlg.result_data:
            self._components[idx] = dlg.result_data
            self._refresh_table()

    def _remove_component(self):
        idx = self._selected_row()
        if idx >= 0:
            self._components.pop(idx)
            self._refresh_table()

    def _move_up(self):
        idx = self._selected_row()
        if idx > 0:
            self._components[idx - 1], self._components[idx] = (
                self._components[idx], self._components[idx - 1]
            )
            self._refresh_table()
            self._table.selectRow(idx - 1)

    def _move_down(self):
        idx = self._selected_row()
        if 0 <= idx < len(self._components) - 1:
            self._components[idx + 1], self._components[idx] = (
                self._components[idx], self._components[idx + 1]
            )
            self._refresh_table()
            self._table.selectRow(idx + 1)

    def _ok(self):
        try:
            num = int(self._num_edit.text()) if self._num_edit.text().strip() else 0
        except ValueError:
            num = 0
        self.result_data = Rung(
            components=[Component(**c) for c in self._components],
            rung_number=num,
            description=self._desc_edit.text().strip(),
        )
        self.accept()


# ---------------------------------------------------------------------------
# IO Dialog
# ---------------------------------------------------------------------------

def _io_fields_def() -> list[tuple[str, str]]:
    """Return I/O form field (label, data_key) pairs in the current language."""
    return [
        (tr("lbl_tag_req"),           "tag"),
        (tr("lbl_address_colon"),     "address"),
        (tr("col_description") + ":", "description"),
        (tr("lbl_panel_cabinet"),     "panel"),
        (tr("lbl_signal_type_colon"), "signal_type"),
        (tr("lbl_terminal_colon"),    "terminal"),
        (tr("lbl_cable_colon"),       "cable"),
        (tr("lbl_notes_colon"),       "notes"),
    ]


class IODialog(QDialog):
    """Add / edit a single I/O list item."""

    def __init__(self, parent=None, data: dict | None = None):
        super().__init__(parent)
        self.setWindowTitle(tr("dlg_io_title"))
        self.setMinimumWidth(380)
        self.result_data: dict | None = None
        self._build(data)

    def _build(self, data: dict | None):
        layout = QVBoxLayout(self)
        form = QFormLayout()
        layout.addLayout(form)

        self._type_cb = QComboBox()
        self._type_cb.addItems(IO_TYPES)
        form.addRow(tr("col_type") + ":", self._type_cb)

        self._entries: dict[str, QLineEdit] = {}
        for label, key in _io_fields_def():
            edit = QLineEdit()
            form.addRow(label, edit)
            self._entries[key] = edit

        if data:
            self._type_cb.setCurrentText(data.get("io_type", "Input"))
            for key, edit in self._entries.items():
                edit.setText(data.get(key, ""))

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self._ok)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _ok(self):
        tag = self._entries["tag"].text().strip()
        if not tag:
            QMessageBox.warning(self, tr("msg_validation"), tr("msg_tag_required"))
            return
        self.result_data = {
            "io_type": self._type_cb.currentText(),
            **{k: e.text().strip() for k, e in self._entries.items()},
        }
        self.accept()


# ---------------------------------------------------------------------------
# IOValues Dialog
# ---------------------------------------------------------------------------

class IOValuesDialog(QDialog):
    """Manage the global list of possible value strings for module other-IOs."""

    def __init__(self, parent=None, values: list[str] | None = None):
        super().__init__(parent)
        self.setWindowTitle(tr("dlg_io_values_title"))
        self.setMinimumWidth(320)
        self.setMinimumHeight(340)
        self.result_values: list[str] | None = None
        self._build(list(values or []))

    def _build(self, values: list[str]):
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(tr("lbl_io_values_hdr")))

        self._list = QListWidget()
        for v in values:
            self._list.addItem(v)
        layout.addWidget(self._list, 1)

        add_row = QWidget()
        add_lay = QHBoxLayout(add_row)
        add_lay.setContentsMargins(0, 0, 0, 0)
        self._value_edit = QLineEdit()
        self._value_edit.setPlaceholderText(tr("lbl_io_value_placeholder"))
        self._btn_add_val = QPushButton(tr("btn_add_io_value"))
        self._btn_add_val.clicked.connect(self._add_value)
        self._value_edit.returnPressed.connect(self._add_value)
        add_lay.addWidget(self._value_edit, 1)
        add_lay.addWidget(self._btn_add_val)
        layout.addWidget(add_row)

        self._btn_remove_val = QPushButton(tr("btn_remove"))
        self._btn_remove_val.clicked.connect(self._remove_value)
        layout.addWidget(self._btn_remove_val)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self._ok)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _add_value(self):
        val = self._value_edit.text().strip()
        if not val:
            return
        self._list.addItem(val)
        self._value_edit.clear()

    def _remove_value(self):
        row = self._list.currentRow()
        if row >= 0:
            self._list.takeItem(row)

    def _ok(self):
        self.result_values = [self._list.item(i).text() for i in range(self._list.count())]
        self.accept()


# ---------------------------------------------------------------------------
# Module Pin Dialog
# ---------------------------------------------------------------------------

class ModulePinDialog(QDialog):
    """Add / edit a single pin entry (name + X, Y position)."""

    def __init__(self, parent=None, data: dict | None = None):
        super().__init__(parent)
        self.setWindowTitle(tr("dlg_module_pin_title"))
        self.setMinimumWidth(320)
        self.result_data: dict | None = None
        self._build(data)

    def _build(self, data: dict | None):
        layout = QVBoxLayout(self)
        form = QFormLayout()
        layout.addLayout(form)

        self._name_edit = QLineEdit()
        form.addRow(tr("lbl_pin_name_colon"), self._name_edit)

        self._x_spin = CoordSpinBox()
        form.addRow("X:", self._x_spin)

        self._y_spin = CoordSpinBox()
        form.addRow("Y:", self._y_spin)

        if data:
            self._name_edit.setText(data.get("name", ""))
            self._x_spin.setValue(float(data.get("x", 0.0)))
            self._y_spin.setValue(float(data.get("y", 0.0)))

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self._ok)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _ok(self):
        self.result_data = {
            "name": self._name_edit.text().strip(),
            "x":    self._x_spin.value(),
            "y":    self._y_spin.value(),
        }
        self.accept()


# ---------------------------------------------------------------------------
# Pin List Widget
# ---------------------------------------------------------------------------

class _PinListWidget(QWidget):
    """Reusable widget: a table of {name, x, y} pins with Add / Edit / Remove."""

    def __init__(self, parent=None):
        super().__init__(parent)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)

        self._table = QTableWidget(0, 3)
        self._table.setHorizontalHeaderLabels([tr("col_pin_name"), "X", "Y"])
        self._table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self._table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self._table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self._table.setSelectionBehavior(QTableWidget.SelectRows)
        self._table.setEditTriggers(QTableWidget.NoEditTriggers)
        self._table.doubleClicked.connect(self._edit_pin)
        lay.addWidget(self._table)

        lay.addWidget(_make_toolbar_row(
            (tr("btn_add_pin"),  self._add_pin),
            (tr("btn_edit_pin"), self._edit_pin),
            (tr("btn_remove"),   self._remove_pin),
        ))

    def set_pins(self, pins: list[dict]):
        self._table.setRowCount(0)
        for pin in pins:
            row = self._table.rowCount()
            self._table.insertRow(row)
            self._table.setItem(row, 0, QTableWidgetItem(pin.get("name", "")))
            self._table.setItem(row, 1, QTableWidgetItem(str(pin.get("x", 0.0))))
            self._table.setItem(row, 2, QTableWidgetItem(str(pin.get("y", 0.0))))

    def get_pins(self) -> list[dict]:
        result = []
        for r in range(self._table.rowCount()):
            try:
                x = float(self._table.item(r, 1).text())
            except (ValueError, AttributeError):
                x = 0.0
            try:
                y = float(self._table.item(r, 2).text())
            except (ValueError, AttributeError):
                y = 0.0
            result.append({
                "name": self._table.item(r, 0).text() if self._table.item(r, 0) else "",
                "x":    x,
                "y":    y,
            })
        return result

    def _selected_row(self) -> int:
        return self._table.currentRow() if self._table.selectedItems() else -1

    def _add_pin(self):
        dlg = ModulePinDialog(self.window())
        if dlg.exec() == QDialog.Accepted and dlg.result_data:
            pins = self.get_pins()
            pins.append(dlg.result_data)
            self.set_pins(pins)

    def _edit_pin(self):
        idx = self._selected_row()
        if idx < 0:
            return
        dlg = ModulePinDialog(self.window(), self.get_pins()[idx])
        if dlg.exec() == QDialog.Accepted and dlg.result_data:
            pins = self.get_pins()
            pins[idx] = dlg.result_data
            self.set_pins(pins)

    def _remove_pin(self):
        idx = self._selected_row()
        if idx >= 0:
            self._table.removeRow(idx)


# ---------------------------------------------------------------------------
# Module Other IO Dialog
# ---------------------------------------------------------------------------

class ModuleOtherIODialog(QDialog):
    """Add / edit a single 'other I/O' entry on a module."""

    def __init__(self, parent=None, data: dict | None = None, io_values: list[str] | None = None):
        super().__init__(parent)
        self.setWindowTitle(tr("dlg_other_io_title"))
        self.setMinimumWidth(380)
        self.result_data: dict | None = None
        self._io_values = io_values or []
        self._build(data)

    def _build(self, data: dict | None):
        layout = QVBoxLayout(self)
        form = QFormLayout()
        layout.addLayout(form)

        self._name_edit = QLineEdit()
        form.addRow(tr("lbl_other_io_name_colon"), self._name_edit)

        self._desc_edit = QLineEdit()
        form.addRow(tr("lbl_other_io_desc_colon"), self._desc_edit)

        self._value_cb = QComboBox()
        self._value_cb.setEditable(True)
        self._value_cb.addItems(self._io_values)
        form.addRow(tr("lbl_other_io_value_colon"), self._value_cb)

        if data:
            self._name_edit.setText(data.get("name", ""))
            self._desc_edit.setText(data.get("description", ""))
            val = data.get("value", "")
            idx = self._value_cb.findText(val)
            if idx >= 0:
                self._value_cb.setCurrentIndex(idx)
            else:
                self._value_cb.setCurrentText(val)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self._ok)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _ok(self):
        name = self._name_edit.text().strip()
        if not name:
            QMessageBox.warning(self, tr("msg_validation"), tr("msg_other_io_name_required"))
            return
        self.result_data = {
            "name":        name,
            "description": self._desc_edit.text().strip(),
            "value":       self._value_cb.currentText().strip(),
        }
        self.accept()


# ---------------------------------------------------------------------------
# Module Dialog
# ---------------------------------------------------------------------------

class ModuleDialog(QDialog):
    """Add / edit a module."""

    def __init__(self, parent=None, data: dict | None = None, io_values: list[str] | None = None,
                 templates: list[str] | None = None):
        super().__init__(parent)
        self.setWindowTitle(tr("dlg_module_title"))
        self.resize(660, 540)
        self.result_data: dict | None = None
        self._io_values = io_values or []
        self._templates = templates or []
        self._other_ios: list[dict] = []
        self._build(data)

    def _build(self, data: dict | None):
        layout = QVBoxLayout(self)

        # ── Basic fields ────────────────────────────────────────────────────
        basic_grp = QGroupBox(tr("grp_module_basic"))
        form = QFormLayout(basic_grp)
        self._name_edit    = QLineEdit()
        self._company_edit = QLineEdit()
        self._desc_edit    = QLineEdit()
        self._template_cb  = QComboBox()
        self._template_cb.addItem("")  # blank = none
        for t in self._templates:
            self._template_cb.addItem(t)
        form.addRow(tr("lbl_module_name_colon"),     self._name_edit)
        form.addRow(tr("lbl_module_company_colon"),  self._company_edit)
        form.addRow(tr("lbl_module_desc_colon"),     self._desc_edit)
        form.addRow(tr("lbl_module_template_colon"), self._template_cb)
        layout.addWidget(basic_grp)

        # ── I/O tabs ────────────────────────────────────────────────────────
        io_tabs = QTabWidget()

        # Inputs tab
        self._inputs_widget = _PinListWidget()
        io_tabs.addTab(self._inputs_widget, tr("grp_module_inputs"))

        # Outputs tab
        self._outputs_widget = _PinListWidget()
        io_tabs.addTab(self._outputs_widget, tr("grp_module_outputs"))

        # Input Commons tab (with shared checkbox)
        ic_container = QWidget()
        ic_lay = QVBoxLayout(ic_container)
        ic_lay.setContentsMargins(0, 4, 0, 0)
        self._shared_cb = QCheckBox(tr("lbl_input_common_shared"))
        ic_lay.addWidget(self._shared_cb)
        self._input_commons_widget = _PinListWidget()
        ic_lay.addWidget(self._input_commons_widget, 1)
        io_tabs.addTab(ic_container, tr("grp_module_input_commons"))

        # Output Commons tab
        self._output_commons_widget = _PinListWidget()
        io_tabs.addTab(self._output_commons_widget, tr("grp_module_output_commons"))

        # Other I/Os tab
        other_container = QWidget()
        other_lay = QVBoxLayout(other_container)
        other_lay.setContentsMargins(0, 4, 0, 0)
        self._other_io_table = QTableWidget(0, 3)
        self._other_io_table.setHorizontalHeaderLabels([
            tr("col_other_io_name"), tr("col_other_io_description"), tr("col_other_io_value"),
        ])
        self._other_io_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self._other_io_table.setSelectionBehavior(QTableWidget.SelectRows)
        self._other_io_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self._other_io_table.doubleClicked.connect(self._edit_other_io)
        other_lay.addWidget(self._other_io_table)
        other_lay.addWidget(_make_toolbar_row(
            (tr("btn_add_other_io"),  self._add_other_io),
            (tr("btn_edit_other_io"), self._edit_other_io),
            (tr("btn_remove"),        self._remove_other_io),
        ))
        io_tabs.addTab(other_container, tr("grp_module_other_ios"))

        layout.addWidget(io_tabs, 1)

        # ── Buttons ─────────────────────────────────────────────────────────
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self._ok)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        # Pre-fill
        if data:
            self._name_edit.setText(data.get("name", ""))
            self._company_edit.setText(data.get("company", ""))
            self._desc_edit.setText(data.get("description", ""))
            tmpl = data.get("template", "")
            idx = self._template_cb.findText(tmpl)
            self._template_cb.setCurrentIndex(idx if idx >= 0 else 0)
            self._inputs_widget.set_pins(data.get("inputs", []))
            self._outputs_widget.set_pins(data.get("outputs", []))
            self._input_commons_widget.set_pins(data.get("input_commons", []))
            self._output_commons_widget.set_pins(data.get("output_commons", []))
            self._shared_cb.setChecked(data.get("input_common_shared", False))
            self._other_ios = list(data.get("other_ios", []))
            self._refresh_other_io_table()

    def _refresh_other_io_table(self):
        self._other_io_table.setRowCount(0)
        for io in self._other_ios:
            row = self._other_io_table.rowCount()
            self._other_io_table.insertRow(row)
            for col, val in enumerate([
                io.get("name", ""), io.get("description", ""), io.get("value", ""),
            ]):
                self._other_io_table.setItem(row, col, QTableWidgetItem(val))

    def _selected_other_io(self) -> int:
        return self._other_io_table.currentRow() if self._other_io_table.selectedItems() else -1

    def _add_other_io(self):
        dlg = ModuleOtherIODialog(self, io_values=self._io_values)
        if dlg.exec() == QDialog.Accepted and dlg.result_data:
            self._other_ios.append(dlg.result_data)
            self._refresh_other_io_table()

    def _edit_other_io(self):
        idx = self._selected_other_io()
        if idx < 0:
            return
        dlg = ModuleOtherIODialog(self, self._other_ios[idx], io_values=self._io_values)
        if dlg.exec() == QDialog.Accepted and dlg.result_data:
            self._other_ios[idx] = dlg.result_data
            self._refresh_other_io_table()

    def _remove_other_io(self):
        idx = self._selected_other_io()
        if idx >= 0:
            self._other_ios.pop(idx)
            self._refresh_other_io_table()

    def _ok(self):
        name = self._name_edit.text().strip()
        if not name:
            QMessageBox.warning(self, tr("msg_validation"), tr("msg_module_name_required"))
            return
        self.result_data = {
            "name":                name,
            "company":             self._company_edit.text().strip(),
            "description":         self._desc_edit.text().strip(),
            "template":            self._template_cb.currentText(),
            "inputs":              self._inputs_widget.get_pins(),
            "outputs":             self._outputs_widget.get_pins(),
            "input_commons":       self._input_commons_widget.get_pins(),
            "output_commons":      self._output_commons_widget.get_pins(),
            "input_common_shared": self._shared_cb.isChecked(),
            "other_ios":           list(self._other_ios),
        }
        self.accept()


# ---------------------------------------------------------------------------
# Rule Dialog
# ---------------------------------------------------------------------------

class RuleDialog(QDialog):
    """Add / edit a single rule."""

    def __init__(self, parent=None, data: dict | None = None):
        super().__init__(parent)
        self.setWindowTitle(tr("dlg_rule_title"))
        self.setMinimumWidth(480)
        self.result_data: dict | None = None
        self._build(data)

    def _build(self, data: dict | None):
        layout = QVBoxLayout(self)
        form = QFormLayout()
        layout.addLayout(form)

        self._name_edit = QLineEdit()
        form.addRow(tr("lbl_rule_name_colon"), self._name_edit)

        self._desc_edit = QLineEdit()
        form.addRow(tr("lbl_rule_desc_colon"), self._desc_edit)

        if data:
            self._name_edit.setText(data.get("name", ""))
            self._desc_edit.setText(data.get("description", ""))

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self._ok)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _ok(self):
        name = self._name_edit.text().strip()
        if not name:
            QMessageBox.warning(self, tr("msg_validation"), tr("msg_rule_name_required"))
            return
        self.result_data = {
            "name":        name,
            "description": self._desc_edit.text().strip(),
        }
        self.accept()


# ---------------------------------------------------------------------------
# Template IO Dialog
# ---------------------------------------------------------------------------

_TMPL_IO_SIGNAL_TYPES = ["Analog", "Digital"]
_TMPL_IO_DIRECTIONS   = ["Input", "Output"]


def _tmpl_io_type(signal: str, direction: str) -> str:
    return f"1 {signal} {direction}"


class TemplateIODialog(QDialog):
    """Add / edit a single I/O entry on a template."""

    def __init__(self, parent=None, data: dict | None = None, io_types: list[dict] | None = None,
                 available_templates: list[str] | None = None):
        super().__init__(parent)
        self.setWindowTitle(tr("dlg_template_io_title"))
        self.setMinimumWidth(400)
        self.result_data: dict | None = None
        self._io_types = io_types or []
        self._available_templates = available_templates or []
        self._build(data)

    def _build(self, data: dict | None):
        layout = QVBoxLayout(self)
        form = QFormLayout()
        layout.addLayout(form)

        self._name_edit = QLineEdit()
        form.addRow(tr("lbl_io_name_colon"), self._name_edit)

        self._desc_edit = QLineEdit()
        form.addRow(tr("col_description") + ":", self._desc_edit)

        self._signal_cb = QComboBox()
        self._signal_cb.addItems(_TMPL_IO_SIGNAL_TYPES)
        form.addRow(tr("col_signal_type") + ":", self._signal_cb)

        self._dir_cb = QComboBox()
        self._dir_cb.addItems(_TMPL_IO_DIRECTIONS)
        form.addRow(tr("lbl_io_direction"), self._dir_cb)

        self._io_type_cb = QComboBox()
        form.addRow(tr("col_io_type") + ":", self._io_type_cb)

        # New ladder fields
        self._ladder_type_cb = QComboBox()
        self._ladder_type_cb.addItem("")  # Allow empty selection
        ladder_types = _load_ladder_types()
        self._ladder_type_cb.addItems(ladder_types)
        form.addRow("Ladder Type:", self._ladder_type_cb)

        self._ladder_template_cb = QComboBox()
        self._ladder_template_cb.addItem("")  # Allow empty selection
        self._ladder_template_cb.addItems(self._available_templates)
        form.addRow("Ladder Template:", self._ladder_template_cb)

        self._signal_cb.currentTextChanged.connect(self._sync_io_type)
        self._dir_cb.currentTextChanged.connect(self._sync_io_type)

        if data:
            self._name_edit.setText(data.get("name", ""))
            self._desc_edit.setText(data.get("description", ""))
            self._signal_cb.setCurrentText(data.get("signal_type", _TMPL_IO_SIGNAL_TYPES[0]))
            self._dir_cb.setCurrentText(data.get("direction", _TMPL_IO_DIRECTIONS[0]))
            if data.get("ladder_type"):
                idx = self._ladder_type_cb.findText(data["ladder_type"])
                if idx >= 0:
                    self._ladder_type_cb.setCurrentIndex(idx)
            if data.get("ladder_template"):
                idx = self._ladder_template_cb.findText(data["ladder_template"])
                if idx >= 0:
                    self._ladder_template_cb.setCurrentIndex(idx)

        self._sync_io_type()

        if data and data.get("io_type"):
            idx = self._io_type_cb.findText(data["io_type"])
            if idx >= 0:
                self._io_type_cb.setCurrentIndex(idx)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self._ok)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _sync_io_type(self):
        sig = self._signal_cb.currentText()
        direction = self._dir_cb.currentText()
        previous = self._io_type_cb.currentText()
        self._io_type_cb.blockSignals(True)
        self._io_type_cb.clear()
        matches = [
            t["name"] for t in self._io_types
            if t.get("signal_category") == sig and t.get("direction") == direction
        ]
        self._io_type_cb.addItems(matches)
        idx = self._io_type_cb.findText(previous)
        if idx >= 0:
            self._io_type_cb.setCurrentIndex(idx)
        self._io_type_cb.blockSignals(False)

    def _ok(self):
        name = self._name_edit.text().strip()
        if not name:
            QMessageBox.warning(self, tr("msg_validation"), tr("msg_io_name_required"))
            return
        self.result_data = {
            "name":              name,
            "description":       self._desc_edit.text().strip(),
            "signal_type":       self._signal_cb.currentText(),
            "direction":         self._dir_cb.currentText(),
            "io_type":           self._io_type_cb.currentText(),
            "ladder_type":       self._ladder_type_cb.currentText(),
            "ladder_template":   self._ladder_template_cb.currentText(),
        }
        self.accept()


# ---------------------------------------------------------------------------
# IO Template Config Dialog
# ---------------------------------------------------------------------------

class IOTemplateConfigDialog(QDialog):
    """Configure I/O channels for an IO template.

    Unlike the regular template I/O section this dialog does not allow adding
    new channels.  Its purpose is to set the signal type (Analog / Digital)
    and direction (Input / Output) for each existing channel.
    """

    def __init__(self, parent=None, template_name: str = "",
                 ios: list[dict] | None = None,
                 io_types: list[dict] | None = None,
                 available_templates: list[str] | None = None):
        super().__init__(parent)
        self.setWindowTitle(tr("dlg_io_template_config_title", name=template_name))
        self.setMinimumWidth(580)
        self.setMinimumHeight(380)
        self.result_ios: list[dict] | None = None
        self._ios: list[dict] = [dict(io) for io in (ios or [])]
        self._io_types = io_types or []
        self._available_templates = available_templates or []
        self._build()

    def _build(self):
        layout = QVBoxLayout(self)

        _cols = [
            tr("col_io_name"),
            tr("col_description"),
            tr("col_signal_type"),
            tr("col_io_direction"),
            tr("col_io_type"),
            "Ladder Type",
            "Ladder Template",
        ]
        self._table = QTableWidget(0, len(_cols))
        self._table.setHorizontalHeaderLabels(_cols)
        self._table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self._table.setSelectionBehavior(QTableWidget.SelectRows)
        self._table.setEditTriggers(QTableWidget.NoEditTriggers)
        self._table.doubleClicked.connect(self._edit_row)
        layout.addWidget(self._table)

        # Edit and Remove only – no Add
        btn_row = QWidget()
        btn_lay = QHBoxLayout(btn_row)
        btn_lay.setContentsMargins(0, 0, 0, 0)
        self._btn_edit = QPushButton(tr("btn_edit_template_io"))
        self._btn_edit.clicked.connect(self._edit_row)
        self._btn_remove = QPushButton(tr("btn_remove"))
        self._btn_remove.clicked.connect(self._remove_row)
        btn_lay.addWidget(self._btn_edit)
        btn_lay.addWidget(self._btn_remove)
        btn_lay.addStretch()
        layout.addWidget(btn_row)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self._ok)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self._refresh_table()

    def _refresh_table(self):
        self._table.setRowCount(0)
        for io in self._ios:
            row = self._table.rowCount()
            self._table.insertRow(row)
            for col, key in enumerate(
                ("name", "description", "signal_type", "direction", "io_type", 
                 "ladder_type", "ladder_template")
            ):
                self._table.setItem(row, col, QTableWidgetItem(io.get(key, "")))

    def _selected_row(self) -> int:
        return self._table.currentRow() if self._table.selectedItems() else -1

    def _edit_row(self):
        idx = self._selected_row()
        if idx < 0:
            return
        dlg = TemplateIODialog(self, self._ios[idx], io_types=self._io_types,
                              available_templates=self._available_templates)
        if dlg.exec() == QDialog.Accepted and dlg.result_data:
            self._ios[idx] = dlg.result_data
            self._refresh_table()

    def _remove_row(self):
        idx = self._selected_row()
        if idx < 0:
            return
        name = self._ios[idx].get("name", "")
        if QMessageBox.question(
            self, tr("msg_remove_template_io_title"),
            tr("msg_remove_template_io", name=name),
        ) == QMessageBox.Yes:
            self._ios.pop(idx)
            self._refresh_table()

    def _ok(self):
        self.result_ios = list(self._ios)
        self.accept()


# ---------------------------------------------------------------------------
# Template Blocks Dialog
# ---------------------------------------------------------------------------

class TemplateBlocksDialog(QDialog):
    """Show all blocks defined in a DXF template and their ATTDEF attributes."""

    def __init__(self, parent=None, template_name: str = "", blocks: list | None = None):
        super().__init__(parent)
        self.setWindowTitle(tr("dlg_blocks_title", name=template_name))
        self.resize(780, 480)
        self._blocks = blocks or []
        self._build()

    def _build(self):
        outer = QVBoxLayout(self)
        splitter = QSplitter(Qt.Horizontal)
        outer.addWidget(splitter)

        # Left: block list
        left = QGroupBox(tr("grp_blocks_list"))
        left_lay = QVBoxLayout(left)
        self._block_list = QListWidget()
        left_lay.addWidget(self._block_list)
        splitter.addWidget(left)

        # Right: attribute table
        right = QGroupBox(tr("grp_block_attribs"))
        right_lay = QVBoxLayout(right)
        self._attrib_table = QTableWidget(0, 4)
        self._attrib_table.setHorizontalHeaderLabels([
            tr("col_attrib_tag"),
            tr("col_attrib_prompt"),
            tr("col_attrib_default"),
            tr("col_attrib_flags"),
        ])
        self._attrib_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self._attrib_table.setSelectionBehavior(QTableWidget.SelectRows)
        self._attrib_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self._status_lbl = QLabel()
        self._status_lbl.setStyleSheet("color: gray;")
        right_lay.addWidget(self._attrib_table)
        right_lay.addWidget(self._status_lbl)
        splitter.addWidget(right)

        splitter.setSizes([240, 520])

        btn_box = QDialogButtonBox(QDialogButtonBox.Close)
        btn_box.rejected.connect(self.reject)
        outer.addWidget(btn_box)

        # Populate block list
        if self._blocks:
            for blk in self._blocks:
                self._block_list.addItem(blk["name"])
            self._block_list.setCurrentRow(0)
        else:
            self._status_lbl.setText(tr("msg_no_blocks"))

        self._block_list.currentRowChanged.connect(self._on_block_selected)
        if self._blocks:
            self._on_block_selected(0)

    def _on_block_selected(self, row: int):
        self._attrib_table.setRowCount(0)
        if row < 0 or row >= len(self._blocks):
            self._status_lbl.setText(tr("msg_select_block"))
            return
        attrs = self._blocks[row]["attributes"]
        if not attrs:
            self._status_lbl.setText(tr("msg_no_attribs"))
            return
        self._status_lbl.setText("")
        for attr in attrs:
            r = self._attrib_table.rowCount()
            self._attrib_table.insertRow(r)
            for col, key in enumerate(("tag", "prompt", "default", "flags")):
                self._attrib_table.setItem(r, col, QTableWidgetItem(attr.get(key, "")))


# ---------------------------------------------------------------------------
# Circuit Dialog
# ---------------------------------------------------------------------------

class CircuitDialog(QDialog):
    """Create or edit a Circuit."""

    def __init__(self, parent=None, available_templates: list[str] | None = None,
                 data: Circuit | None = None):
        super().__init__(parent)
        self.setWindowTitle(tr("dlg_circuit_title"))
        self.setMinimumWidth(500)
        self.result_circuit: Circuit | None = None
        self._available = available_templates or []
        self._templates: list[Template | str] = []  # Store template objects or strings
        self._build(data)

    def _build(self, data: Circuit | None):
        layout = QVBoxLayout(self)

        # ── Fields ────────────────────────────────────────────────────────
        form = QFormLayout()
        self._e_name   = QLineEdit(data.name           if data else "")
        self._e_number = QLineEdit(data.circuit_number if data else "")
        self._e_desc   = QLineEdit(data.description    if data else "")
        self._lbl_name   = QLabel()
        self._lbl_number = QLabel()
        self._lbl_desc   = QLabel()
        form.addRow(self._lbl_name,   self._e_name)
        form.addRow(self._lbl_number, self._e_number)
        form.addRow(self._lbl_desc,   self._e_desc)
        layout.addLayout(form)

        # ── Template list ──────────────────────────────────────────────────
        self._grp_templates = QGroupBox()
        grp_lay = QVBoxLayout(self._grp_templates)

        # Picker + Add button
        pick_row = QWidget()
        pick_lay = QHBoxLayout(pick_row)
        pick_lay.setContentsMargins(0, 0, 0, 0)
        self._tmpl_picker = QComboBox()
        self._tmpl_picker.addItems(self._available)
        self._btn_add_tmpl = QPushButton()
        self._btn_add_tmpl.clicked.connect(self._add_template)
        pick_lay.addWidget(self._tmpl_picker, 1)
        pick_lay.addWidget(self._btn_add_tmpl)
        grp_lay.addWidget(pick_row)

        self._tmpl_list = QListWidget()
        # Initialize from existing circuit templates
        if data:
            self._templates = list(data.templates) if data.templates else []
            for tmpl in self._templates:
                display_text = self._format_template_display(tmpl)
                self._tmpl_list.addItem(display_text)
        grp_lay.addWidget(self._tmpl_list, 1)

        # Remove / Up / Down
        ctrl_row = QWidget()
        ctrl_lay = QHBoxLayout(ctrl_row)
        ctrl_lay.setContentsMargins(0, 0, 0, 0)
        self._btn_remove_tmpl = QPushButton()
        self._btn_tmpl_up     = QPushButton()
        self._btn_tmpl_down   = QPushButton()
        self._btn_remove_tmpl.clicked.connect(self._remove_template)
        self._btn_tmpl_up.clicked.connect(self._move_template_up)
        self._btn_tmpl_down.clicked.connect(self._move_template_down)
        ctrl_lay.addWidget(self._btn_remove_tmpl)
        ctrl_lay.addWidget(self._btn_tmpl_up)
        ctrl_lay.addWidget(self._btn_tmpl_down)
        ctrl_lay.addStretch()
        grp_lay.addWidget(ctrl_row)

        layout.addWidget(self._grp_templates, 1)

        # ── Buttons ────────────────────────────────────────────────────────
        btn_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btn_box.accepted.connect(self._accept)
        btn_box.rejected.connect(self.reject)
        layout.addWidget(btn_box)

        self._retranslate()

    def _format_template_display(self, tmpl: Template | str) -> str:
        """Format a template for display in the list widget."""
        if isinstance(tmpl, Template):
            parts = [tmpl.name]
            if tmpl.ladder_type:
                parts.append(f"[Type: {tmpl.ladder_type}]")
            if tmpl.part_of_ladder:
                parts.append(f"[Rung: {tmpl.part_of_ladder}]")
            return " ".join(parts)
        else:
            # Legacy string template
            return str(tmpl)

    def _retranslate(self):
        self.setWindowTitle(tr("dlg_circuit_title"))
        self._lbl_name.setText(tr("lbl_circuit_name"))
        self._lbl_number.setText(tr("lbl_circuit_number"))
        self._lbl_desc.setText(tr("lbl_circuit_desc"))
        self._grp_templates.setTitle(tr("grp_circuit_templates"))
        self._btn_add_tmpl.setText(tr("btn_add_template"))
        self._btn_remove_tmpl.setText(tr("btn_remove"))
        self._btn_tmpl_up.setText(tr("btn_move_up"))
        self._btn_tmpl_down.setText(tr("btn_move_down"))

    def _add_template(self):
        name = self._tmpl_picker.currentText()
        if not name:
            return
        
        # Show metadata dialog
        dlg = TemplateMetadataDialog(self, template_name=name)
        if dlg.exec() == QDialog.Accepted and dlg.result_template:
            # Add the Template object
            tmpl = dlg.result_template
            self._templates.append(tmpl)
            display_text = self._format_template_display(tmpl)
            self._tmpl_list.addItem(display_text)
        else:
            # User cancelled, add as simple string template
            self._templates.append(name)
            self._tmpl_list.addItem(name)

    def _remove_template(self):
        row = self._tmpl_list.currentRow()
        if row >= 0:
            self._tmpl_list.takeItem(row)
            self._templates.pop(row)

    def _move_template_up(self):
        row = self._tmpl_list.currentRow()
        if row > 0:
            # Swap in both lists
            self._templates[row], self._templates[row - 1] = self._templates[row - 1], self._templates[row]
            item = self._tmpl_list.takeItem(row)
            self._tmpl_list.insertItem(row - 1, item)
            self._tmpl_list.setCurrentRow(row - 1)

    def _move_template_down(self):
        row = self._tmpl_list.currentRow()
        if row >= 0 and row < self._tmpl_list.count() - 1:
            # Swap in both lists
            self._templates[row], self._templates[row + 1] = self._templates[row + 1], self._templates[row]
            item = self._tmpl_list.takeItem(row)
            self._tmpl_list.insertItem(row + 1, item)
            self._tmpl_list.setCurrentRow(row + 1)

    def _accept(self):
        name = self._e_name.text().strip()
        if not name:
            QMessageBox.warning(self, tr("msg_validation"), tr("msg_circuit_name_required"))
            return
        
        self.result_circuit = Circuit(
            name=name,
            circuit_number=self._e_number.text().strip(),
            description=self._e_desc.text().strip(),
            templates=self._templates,
        )
        self.accept()


# ---------------------------------------------------------------------------
# Valve IO Dialog  (add / edit a single ValveIO on a valve type)
# ---------------------------------------------------------------------------

class ValveIODialog(QDialog):
    """Add or edit a single I/O signal for a valve type.

    Uses the same signal-type / direction / io-type combo logic as
    TemplateIODialog so valve IOs stay consistent with the template IO library.
    """

    def __init__(self, parent=None, data: dict | None = None,
                 io_types: list[dict] | None = None):
        super().__init__(parent)
        self.setWindowTitle(tr("dlg_valve_io_title"))
        self.setMinimumWidth(360)
        self.result_data: dict | None = None
        self._io_types = io_types or []
        self._build(data)

    def _build(self, data: dict | None):
        layout = QVBoxLayout(self)
        form = QFormLayout()
        layout.addLayout(form)

        self._name_edit = QLineEdit()
        form.addRow(tr("lbl_io_name_colon"), self._name_edit)

        self._desc_edit = QLineEdit()
        form.addRow(tr("col_description") + ":", self._desc_edit)

        self._signal_cb = QComboBox()
        self._signal_cb.addItems(_TMPL_IO_SIGNAL_TYPES)
        form.addRow(tr("col_signal_type") + ":", self._signal_cb)

        self._dir_cb = QComboBox()
        self._dir_cb.addItems(_TMPL_IO_DIRECTIONS)
        form.addRow(tr("lbl_io_direction"), self._dir_cb)

        self._io_type_cb = QComboBox()
        form.addRow(tr("col_io_type") + ":", self._io_type_cb)

        self._signal_cb.currentTextChanged.connect(self._sync_io_type)
        self._dir_cb.currentTextChanged.connect(self._sync_io_type)

        if data:
            self._name_edit.setText(data.get("name", ""))
            self._desc_edit.setText(data.get("description", ""))
            self._signal_cb.setCurrentText(
                data.get("signal_type", _TMPL_IO_SIGNAL_TYPES[0]))
            self._dir_cb.setCurrentText(
                data.get("direction", _TMPL_IO_DIRECTIONS[0]))

        self._sync_io_type()

        if data and data.get("io_type"):
            idx = self._io_type_cb.findText(data["io_type"])
            if idx >= 0:
                self._io_type_cb.setCurrentIndex(idx)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self._ok)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _sync_io_type(self):
        sig = self._signal_cb.currentText()
        direction = self._dir_cb.currentText()
        previous = self._io_type_cb.currentText()
        self._io_type_cb.blockSignals(True)
        self._io_type_cb.clear()
        matches = [
            t["name"] for t in self._io_types
            if t.get("signal_category") == sig and t.get("direction") == direction
        ]
        self._io_type_cb.addItems(matches)
        idx = self._io_type_cb.findText(previous)
        if idx >= 0:
            self._io_type_cb.setCurrentIndex(idx)
        self._io_type_cb.blockSignals(False)

    def _ok(self):
        name = self._name_edit.text().strip()
        if not name:
            QMessageBox.warning(self, tr("msg_validation"), tr("msg_io_name_required"))
            return
        self.result_data = {
            "name":        name,
            "description": self._desc_edit.text().strip(),
            "signal_type": self._signal_cb.currentText(),
            "direction":   self._dir_cb.currentText(),
            "io_type":     self._io_type_cb.currentText(),
        }
        self.accept()


# ---------------------------------------------------------------------------
# IO Type Dialog  (add / edit a single IO type entry in the library)
# ---------------------------------------------------------------------------

class IOTypeDialog(QDialog):
    """Add or edit a single IO type definition."""

    _SIGNAL_CATEGORIES = ["Analog", "Digital"]
    _DIRECTIONS        = ["Input", "Output"]

    def __init__(self, parent=None, data: dict | None = None,
                 io_templates: list[str] | None = None):
        super().__init__(parent)
        self.setWindowTitle(tr("dlg_io_type_title"))
        self.setMinimumWidth(400)
        self.result_data: dict | None = None
        self._io_templates = io_templates or []
        self._build(data)

    def _build(self, data: dict | None):
        layout = QVBoxLayout(self)
        form = QFormLayout()
        layout.addLayout(form)

        self._name_edit = QLineEdit()
        form.addRow(tr("lbl_io_type_name_colon"), self._name_edit)

        self._desc_edit = QLineEdit()
        form.addRow(tr("col_description") + ":", self._desc_edit)

        self._signal_cb = QComboBox()
        self._signal_cb.addItems(self._SIGNAL_CATEGORIES)
        form.addRow(tr("col_signal_type") + ":", self._signal_cb)

        self._dir_cb = QComboBox()
        self._dir_cb.addItems(self._DIRECTIONS)
        form.addRow(tr("lbl_io_direction"), self._dir_cb)

        self._tmpl_cb = QComboBox()
        self._tmpl_cb.setEditable(True)
        self._tmpl_cb.addItem("")
        self._tmpl_cb.addItems(self._io_templates)
        form.addRow(tr("lbl_io_type_template_colon"), self._tmpl_cb)

        # ── Shared input section ──────────────────────────────────────────────
        self._shared_chk = QCheckBox()
        self._shared_chk.setText(tr("lbl_io_type_shared"))
        self._shared_row_lbl = QLabel(tr("lbl_io_type_shared_colon"))
        form.addRow(self._shared_row_lbl, self._shared_chk)

        self._shared_tmpl_cb = QComboBox()
        self._shared_tmpl_cb.setEditable(True)
        self._shared_tmpl_cb.addItem("")
        self._shared_tmpl_cb.addItems(self._io_templates)
        self._shared_tmpl_lbl = QLabel(tr("lbl_io_type_shared_template_colon"))
        form.addRow(self._shared_tmpl_lbl, self._shared_tmpl_cb)

        self._dir_cb.currentTextChanged.connect(self._sync_shared_visibility)
        self._shared_chk.toggled.connect(self._sync_shared_visibility)

        if data:
            self._name_edit.setText(data.get("name", ""))
            self._desc_edit.setText(data.get("description", ""))
            self._signal_cb.setCurrentText(data.get("signal_category", self._SIGNAL_CATEGORIES[0]))
            self._dir_cb.setCurrentText(data.get("direction", self._DIRECTIONS[0]))
            tmpl_val = data.get("io_template", "")
            idx = self._tmpl_cb.findText(tmpl_val)
            if idx >= 0:
                self._tmpl_cb.setCurrentIndex(idx)
            else:
                self._tmpl_cb.setCurrentText(tmpl_val)
            self._shared_chk.setChecked(bool(data.get("shared", False)))
            shared_tmpl = data.get("shared_template", "")
            sidx = self._shared_tmpl_cb.findText(shared_tmpl)
            if sidx >= 0:
                self._shared_tmpl_cb.setCurrentIndex(sidx)
            else:
                self._shared_tmpl_cb.setCurrentText(shared_tmpl)

        self._sync_shared_visibility()

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self._ok)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _sync_shared_visibility(self):
        is_input = self._dir_cb.currentText() == "Input"
        self._shared_row_lbl.setVisible(is_input)
        self._shared_chk.setVisible(is_input)
        show_shared_tmpl = is_input and self._shared_chk.isChecked()
        self._shared_tmpl_lbl.setVisible(show_shared_tmpl)
        self._shared_tmpl_cb.setVisible(show_shared_tmpl)
        if not is_input:
            self._shared_chk.setChecked(False)

    def _ok(self):
        name = self._name_edit.text().strip()
        if not name:
            QMessageBox.warning(self, tr("msg_validation"), tr("msg_io_type_name_required"))
            return
        is_input = self._dir_cb.currentText() == "Input"
        shared = is_input and self._shared_chk.isChecked()
        self.result_data = {
            "name":            name,
            "description":     self._desc_edit.text().strip(),
            "signal_category": self._signal_cb.currentText(),
            "direction":       self._dir_cb.currentText(),
            "io_template":     self._tmpl_cb.currentText().strip(),
            "shared":          shared,
            "shared_template": self._shared_tmpl_cb.currentText().strip() if shared else "",
        }
        self.accept()


# ---------------------------------------------------------------------------
# Valve Dialog  (add / edit a valve instance in the project)
# ---------------------------------------------------------------------------

class ValveDialog(QDialog):
    """Add or edit a valve instance."""

    def __init__(self, parent=None, valve_types: list[str] | None = None,
                 circuits: list[str] | None = None,
                 circuit_locked: str | None = None,
                 data: dict | None = None):
        """
        Parameters
        ----------
        valve_types     : selectable valve type names
        circuits        : all circuit names (for the circuit combo)
        circuit_locked  : when set, pre-select this circuit and hide the combo
                          (used when adding from a filtered view)
        data            : pre-fill dict for editing
        """
        super().__init__(parent)
        self.result_data: dict | None = None
        self._circuit_locked = circuit_locked
        self._build_ui(valve_types or [], circuits or [], data or {})

    def _build_ui(self, valve_types: list[str], circuits: list[str], data: dict):
        layout = QFormLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)

        # Show auto-generated ID as read-only when editing an existing valve
        existing_id = data.get("tag", "")
        if existing_id:
            lbl_id = QLabel(f"<b>{existing_id}</b>")
            layout.addRow(tr("lbl_valve_id"), lbl_id)

        self._e_desc = QLineEdit(data.get("description", ""))

        self._cb_type = QComboBox()
        self._cb_type.addItems(valve_types)
        if data.get("valve_type") in valve_types:
            self._cb_type.setCurrentText(data["valve_type"])

        self._cb_circuit = QComboBox()
        self._cb_circuit.addItems(circuits)
        preselect = self._circuit_locked or data.get("circuit_name", "")
        if preselect:
            idx = self._cb_circuit.findText(preselect)
            if idx >= 0:
                self._cb_circuit.setCurrentIndex(idx)

        layout.addRow(tr("lbl_valve_type"),  self._cb_type)
        layout.addRow(tr("col_description"), self._e_desc)
        if not self._circuit_locked:
            layout.addRow(tr("lbl_valve_circuit"), self._cb_circuit)

        btn_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btn_box.accepted.connect(self._accept)
        btn_box.rejected.connect(self.reject)
        layout.addRow(btn_box)

        self.setWindowTitle(tr("dlg_valve_title"))

    def _accept(self):
        circuit_name = self._circuit_locked or self._cb_circuit.currentText()
        self.result_data = {
            "valve_type":   self._cb_type.currentText(),
            "description":  self._e_desc.text().strip(),
            "circuit_name": circuit_name,
        }
        self.accept()


# ---------------------------------------------------------------------------
# Generation Progress Dialog
# ---------------------------------------------------------------------------

class GenerationProgressDialog(QDialog):
    """Non-modal progress dialog showing generation progress with cancel option."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(tr("dlg_generation_progress") if hasattr(tr, '__call__') else "Generation Progress")
        self.setMinimumWidth(400)
        self.setMinimumHeight(150)
        self.setModal(False)
        self.cancelled = False
        self._build()

    def _build(self):
        layout = QVBoxLayout(self)
        
        self._lbl_status = QLabel("Initializing...")
        layout.addWidget(self._lbl_status)
        
        self._progress = QProgressBar()
        self._progress.setMinimum(0)
        self._progress.setMaximum(100)
        self._progress.setValue(0)
        layout.addWidget(self._progress)
        
        self._lbl_detail = QLabel("")
        self._lbl_detail.setStyleSheet("color: gray; font-size: 10px;")
        layout.addWidget(self._lbl_detail)
        
        layout.addStretch()
        
        self._btn_cancel = QPushButton("Cancel")
        self._btn_cancel.clicked.connect(self._on_cancel)
        layout.addWidget(self._btn_cancel)

    def _on_cancel(self):
        self.cancelled = True
        self._btn_cancel.setEnabled(False)
        self._btn_cancel.setText("Cancelling...")

    def update_progress(self, current: int, total: int, message: str = "", detail: str = ""):
        """Update progress bar and status message.
        
        Args:
            current: Current step number (0-based)
            total: Total number of steps
            message: Main status message
            detail: Optional detail text
        """
        if total > 0:
            percentage = int((current / total) * 100)
            self._progress.setValue(percentage)
        
        if message:
            self._lbl_status.setText(message)
        
        if detail:
            self._lbl_detail.setText(detail)
        
        # Process events to keep UI responsive
        from PySide6.QtWidgets import QApplication
        QApplication.processEvents()

    def set_status(self, message: str, detail: str = ""):
        """Set status message without updating progress."""
        self._lbl_status.setText(message)
        if detail:
            self._lbl_detail.setText(detail)
        from PySide6.QtWidgets import QApplication
        QApplication.processEvents()

