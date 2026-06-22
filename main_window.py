"""
Main application window for the AutoCAD Electrical Drawing Generator.
"""
from __future__ import annotations

import dataclasses
import json
import math
import os
import sys
from pathlib import Path

from PySide6.QtCore import Qt, QRectF, QThread
from PySide6.QtGui import QAction, QFont, QPixmap
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QSplitter,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from template_manager import TemplateManager, CTRL_TEMPLATES_DIR, IO_TEMPLATES_DIR, _find_oda_converter, convert_dxf_to_dwg, convert_folder_dxf_to_dwg
from drawing_generator import DrawingGenerator, LadderConfig, Rung, Component
from io_manager import IOItem
from i18n import tr, set_language, available_languages
import project_manager as pm
import circuit_library as cl
import rules_manager as rl
import module_manager as mm

from models import Circuit, Valve
from preview_widget import PreviewWorker, ZoomablePreview
from dialogs import (
    _make_toolbar_row,
    CoordSpinBox,
    ComponentDialog,
    RungDialog,
    IODialog,
    IOValuesDialog,
    ModuleDialog,
    RuleDialog,
    TemplateIODialog,
    IOTemplateConfigDialog,
    CircuitDialog,
    ValveDialog,
    ValveIODialog,
    IOTypeDialog,
)
import valve_manager as vm


# ---------------------------------------------------------------------------
# Table column definitions
# ---------------------------------------------------------------------------

_PAPER_SIZES = {
    "A4 Portrait":  (210, 297),
    "A4 Landscape": (297, 210),
    "A3 Landscape": (420, 297),
    "A3 Portrait":  (297, 420),
    "A1 Landscape": (841, 594),
    "A0 Landscape": (1189, 841),
}

_IO_COLS   = ("Circuit", "Circuit No", "Template", "Name", "Description", "Signal Type", "Direction", "IO Type")
_IO_WIDTHS = (120, 80, 110, 110, 180, 90, 80, 130)

_TMPL_IO_COLS   = ("Name", "Description", "Signal Type", "Direction", "IO Type")
_TMPL_IO_WIDTHS = (120, 200, 90, 80, 130)




# ---------------------------------------------------------------------------
# Main window
# ---------------------------------------------------------------------------

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.resize(1200, 780)

        self._template_mgr = TemplateManager()
        self._ctrl_template_mgr = TemplateManager(CTRL_TEMPLATES_DIR)
        self._io_template_mgr = TemplateManager(IO_TEMPLATES_DIR)
        self._active_template_mgr = self._template_mgr
        self._rungs: list[Rung] = []
        self._io_items: list[IOItem] = []
        self._library_circuits: list[Circuit] = []      # global – shared across projects
        self._project_circuit_refs: list[str] = []      # per-project (names, may repeat)
        self._rules: list[dict] = []                    # global rules library
        self._modules: list[dict] = []                  # global modules library
        self._module_io_values: list[str] = []          # possible values for module other-IOs
        self._io_types: list[dict] = []                 # global IO types library
        self._valve_types: list[str] = []               # global valve type names
        self._valve_rows: list[tuple[int, int]] = []    # (circuit_idx, valve_idx) per table row
        self._tmpl_blocks: list[dict] = []
        self._tmpl_attr_values: dict[str, dict[str, str]] = {}
        self._tmpl_current_block: str | None = None
        self._tmpl_ios: list[dict] = []
        self._tmpl_current_name: str | None = None
        self._active_tmpl_type: str = "regular"  # "regular" | "controller" | "io"
        self._preview_worker: PreviewWorker | None = None
        self._preview_thread: QThread | None = None
        self._preview_generation: int = 0
        self._preview_fit_on_next: bool = True
        self._tmpl_axis_bounds: tuple[float, float, float, float] | None = None
        self._project_path: str | None = None   # current .aepj file path
        self._dirty: bool = False               # unsaved changes?

        self._build_menu()
        self._build_ui()
        self._tmpl_preview_lbl.zoom_changed.connect(self._on_preview_zoom_changed)
        self._refresh_template_list()
        self._refresh_ctrl_template_list()
        self._refresh_io_template_list()
        self._load_library()
        self._load_rules()
        self._load_modules()
        self._load_io_types()
        self._load_valve_config()
        self._retranslate_ui()
        self._update_window_title()

    # ── Menu ─────────────────────────────────────────────────────────────────

    def _build_menu(self):
        mb = self.menuBar()

        self._menu_file = mb.addMenu("")
        self._act_new = QAction("", self)
        self._act_new.triggered.connect(self._new_drawing)
        self._menu_file.addAction(self._act_new)
        self._menu_file.addSeparator()
        self._act_open_project = QAction("", self)
        self._act_open_project.triggered.connect(self._open_project)
        self._menu_file.addAction(self._act_open_project)
        self._act_save_project = QAction("", self)
        self._act_save_project.triggered.connect(self._save_project)
        self._menu_file.addAction(self._act_save_project)
        self._act_save_project_as = QAction("", self)
        self._act_save_project_as.triggered.connect(self._save_project_as)
        self._menu_file.addAction(self._act_save_project_as)
        self._menu_file.addSeparator()
        self._act_exit = QAction("", self)
        self._act_exit.triggered.connect(self.close)
        self._menu_file.addAction(self._act_exit)

        self._menu_templates = mb.addMenu("")
        self._act_import_tmpl = QAction("", self)
        self._act_import_tmpl.triggered.connect(self._import_template)
        self._menu_templates.addAction(self._act_import_tmpl)
        self._act_del_tmpl = QAction("", self)
        self._act_del_tmpl.triggered.connect(self._delete_template)
        self._menu_templates.addAction(self._act_del_tmpl)

        self._menu_lang = mb.addMenu("")
        for code, name in available_languages().items():
            act = QAction(name, self)
            act.triggered.connect(lambda checked=False, c=code: self._change_language(c))
            self._menu_lang.addAction(act)

        self._menu_help = mb.addMenu("")
        self._act_about = QAction("", self)
        self._act_about.triggered.connect(self._about)
        self._menu_help.addAction(self._act_about)

    # ── Main layout ───────────────────────────────────────────────────────────

    def _build_ui(self):
        splitter = QSplitter(Qt.Horizontal)
        self.setCentralWidget(splitter)
        splitter.addWidget(self._build_left())
        splitter.setStretchFactor(0, 0)
        splitter.addWidget(self._build_right())
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([300, 900])

    # ── Left panel ────────────────────────────────────────────────────────────

    def _build_left(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(6, 6, 6, 6)

        self._grp_settings = QGroupBox()
        form = QFormLayout(self._grp_settings)
        self._e_title   = QLineEdit("ELECTRICAL DRAWING")
        self._e_project = QLineEdit()
        self._e_dwgno   = QLineEdit("001")
        self._e_rev     = QLineEdit("A")
        self._e_drawnby = QLineEdit()
        self._paper_cb  = QComboBox()
        self._paper_cb.addItems(list(_PAPER_SIZES.keys()))
        self._paper_cb.setCurrentText("A3 Landscape")
        self._lbl_title_w      = QLabel()
        self._lbl_project_w    = QLabel()
        self._lbl_drawing_no_w = QLabel()
        self._lbl_revision_w   = QLabel()
        self._lbl_drawn_by_w   = QLabel()
        self._lbl_paper_size_w = QLabel()
        self._lbl_module_w = QLabel()
        self._module_cb = QComboBox()
        form.addRow(self._lbl_title_w,      self._e_title)
        form.addRow(self._lbl_project_w,    self._e_project)
        form.addRow(self._lbl_drawing_no_w, self._e_dwgno)
        form.addRow(self._lbl_revision_w,   self._e_rev)
        form.addRow(self._lbl_drawn_by_w,   self._e_drawnby)
        form.addRow(self._lbl_paper_size_w, self._paper_cb)
        form.addRow(self._lbl_module_w,     self._module_cb)
        layout.addWidget(self._grp_settings)

        self._lbl_io_summary = QLabel()
        self._lbl_io_summary.setStyleSheet("color: gray; font-size: 11px;")
        self._lbl_io_summary.setAlignment(Qt.AlignCenter)
        self._lbl_io_summary.setWordWrap(True)
        layout.addWidget(self._lbl_io_summary)

        self._btn_generate = QPushButton()
        self._btn_generate.setMinimumHeight(36)
        f = self._btn_generate.font()
        f.setBold(True)
        self._btn_generate.setFont(f)
        self._btn_generate.clicked.connect(self._generate)
        layout.addWidget(self._btn_generate)

        return panel

    # ── Right panel ───────────────────────────────────────────────────────────

    def _build_right(self) -> QWidget:
        self._tabs = QTabWidget()
        self._tabs.addTab(self._build_io_tab(), "")
        self._tabs.addTab(self._build_template_tab(), "")
        self._tabs.addTab(self._build_circuits_tab(), "")
        self._tabs.addTab(self._build_rules_tab(), "")
        self._tabs.addTab(self._build_modules_tab(), "")
        self._tabs.addTab(self._build_valves_tab(), "")
        self._tabs.addTab(self._build_io_types_tab(), "")
        return self._tabs

    # ── I/O tab ───────────────────────────────────────────────────────────────

    def _build_io_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)

        header = QWidget()
        h_lay = QHBoxLayout(header)
        h_lay.setContentsMargins(0, 0, 0, 0)
        self._lbl_io_hdr = QLabel()
        self._lbl_io_hdr.setFont(QFont("", 11, QFont.Bold))
        h_lay.addWidget(self._lbl_io_hdr)
        h_lay.addStretch()
        self._btn_refresh_io = QPushButton()
        self._btn_refresh_io.clicked.connect(self._refresh_io_table)
        h_lay.addWidget(self._btn_refresh_io)
        layout.addWidget(header)

        self._io_table = QTableWidget(0, len(_IO_COLS))
        for i, w in enumerate(_IO_WIDTHS):
            self._io_table.setColumnWidth(i, w)
        self._io_table.horizontalHeader().setStretchLastSection(True)
        self._io_table.setSelectionBehavior(QTableWidget.SelectRows)
        self._io_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self._io_table.doubleClicked.connect(self._edit_io)
        layout.addWidget(self._io_table)
        return widget

    # ── Template tab ──────────────────────────────────────────────────────────

    def _build_template_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(6, 6, 6, 6)

        # ── Template type selector (3 sub-tabs: Regular / Controller / IO) ─────
        self._tmpl_type_tabs = QTabWidget()

        # Tab 0: Regular templates
        tab0 = QWidget()
        t0_lay = QVBoxLayout(tab0)
        t0_lay.setContentsMargins(4, 4, 4, 4)
        self._tmpl_list = QListWidget()
        self._tmpl_list.currentItemChanged.connect(self._on_template_selected)
        t0_lay.addWidget(self._tmpl_list)
        t0_btn = QWidget()
        t0_btn_lay = QHBoxLayout(t0_btn)
        t0_btn_lay.setContentsMargins(0, 0, 0, 0)
        self._btn_import_tmpl = QPushButton()
        self._btn_import_tmpl.clicked.connect(self._import_template)
        self._btn_delete_tmpl = QPushButton()
        self._btn_delete_tmpl.clicked.connect(self._delete_template)
        self._btn_open_tmpl_folder = QPushButton()
        self._btn_open_tmpl_folder.clicked.connect(self._open_template_folder)
        t0_btn_lay.addWidget(self._btn_import_tmpl)
        t0_btn_lay.addWidget(self._btn_delete_tmpl)
        t0_btn_lay.addWidget(self._btn_open_tmpl_folder)
        t0_btn_lay.addStretch()
        t0_lay.addWidget(t0_btn)
        self._tmpl_type_tabs.addTab(tab0, "")

        # Tab 1: Controller templates
        tab1 = QWidget()
        t1_lay = QVBoxLayout(tab1)
        t1_lay.setContentsMargins(4, 4, 4, 4)
        self._ctrl_tmpl_list = QListWidget()
        self._ctrl_tmpl_list.currentItemChanged.connect(self._on_ctrl_template_selected)
        t1_lay.addWidget(self._ctrl_tmpl_list)
        t1_btn = QWidget()
        t1_btn_lay = QHBoxLayout(t1_btn)
        t1_btn_lay.setContentsMargins(0, 0, 0, 0)
        self._btn_import_ctrl_tmpl = QPushButton()
        self._btn_import_ctrl_tmpl.clicked.connect(self._import_ctrl_template)
        self._btn_delete_ctrl_tmpl = QPushButton()
        self._btn_delete_ctrl_tmpl.clicked.connect(self._delete_ctrl_template)
        self._btn_open_ctrl_tmpl_folder = QPushButton()
        self._btn_open_ctrl_tmpl_folder.clicked.connect(self._open_ctrl_template_folder)
        t1_btn_lay.addWidget(self._btn_import_ctrl_tmpl)
        t1_btn_lay.addWidget(self._btn_delete_ctrl_tmpl)
        t1_btn_lay.addWidget(self._btn_open_ctrl_tmpl_folder)
        t1_btn_lay.addStretch()
        t1_lay.addWidget(t1_btn)
        self._tmpl_type_tabs.addTab(tab1, "")

        # Tab 2: IO templates
        tab2 = QWidget()
        t2_lay = QVBoxLayout(tab2)
        t2_lay.setContentsMargins(4, 4, 4, 4)
        self._io_tmpl_list = QListWidget()
        self._io_tmpl_list.currentItemChanged.connect(self._on_io_template_selected)
        self._io_tmpl_list.itemDoubleClicked.connect(self._open_io_template_config)
        t2_lay.addWidget(self._io_tmpl_list)
        t2_btn = QWidget()
        t2_btn_lay = QHBoxLayout(t2_btn)
        t2_btn_lay.setContentsMargins(0, 0, 0, 0)
        self._btn_import_io_tmpl = QPushButton()
        self._btn_import_io_tmpl.clicked.connect(self._import_io_template)
        self._btn_delete_io_tmpl = QPushButton()
        self._btn_delete_io_tmpl.clicked.connect(self._delete_io_template)
        self._btn_open_io_tmpl_folder = QPushButton()
        self._btn_open_io_tmpl_folder.clicked.connect(self._open_io_template_folder)
        t2_btn_lay.addWidget(self._btn_import_io_tmpl)
        t2_btn_lay.addWidget(self._btn_delete_io_tmpl)
        t2_btn_lay.addWidget(self._btn_open_io_tmpl_folder)
        t2_btn_lay.addStretch()
        t2_lay.addWidget(t2_btn)
        ins_row = QWidget()
        ins_lay = QHBoxLayout(ins_row)
        ins_lay.setContentsMargins(0, 0, 0, 0)
        self._lbl_io_tmpl_ins_x = QLabel()
        self._io_tmpl_ins_x = CoordSpinBox()
        self._lbl_io_tmpl_ins_y = QLabel()
        self._io_tmpl_ins_y = CoordSpinBox()
        ins_lay.addWidget(self._lbl_io_tmpl_ins_x)
        ins_lay.addWidget(self._io_tmpl_ins_x)
        ins_lay.addWidget(self._lbl_io_tmpl_ins_y)
        ins_lay.addWidget(self._io_tmpl_ins_y)
        t2_lay.addWidget(ins_row)
        self._io_tmpl_ins_x.valueChanged.connect(self._on_io_tmpl_ins_changed)
        self._io_tmpl_ins_y.valueChanged.connect(self._on_io_tmpl_ins_changed)
        self._tmpl_type_tabs.addTab(tab2, "")

        layout.addWidget(self._tmpl_type_tabs, 1)

        # ── Preview ───────────────────────────────────────────────────────────
        self._grp_tmpl_preview = QGroupBox()
        prev_lay = QVBoxLayout(self._grp_tmpl_preview)
        prev_lay.setContentsMargins(4, 4, 4, 4)
        self._tmpl_preview_lbl = ZoomablePreview()
        prev_lay.addWidget(self._tmpl_preview_lbl)
        layout.addWidget(self._grp_tmpl_preview, 2)

        # ── Blocks + Attributes splitter ──────────────────────────────────────
        blocks_splitter = QSplitter(Qt.Horizontal)

        self._grp_tmpl_blocks = QGroupBox()
        blk_lay = QVBoxLayout(self._grp_tmpl_blocks)
        self._tmpl_block_list = QListWidget()
        self._tmpl_block_list.currentRowChanged.connect(self._on_tmpl_block_selected)
        blk_lay.addWidget(self._tmpl_block_list)
        blocks_splitter.addWidget(self._grp_tmpl_blocks)

        self._grp_tmpl_attribs = QGroupBox()
        attr_lay = QVBoxLayout(self._grp_tmpl_attribs)
        self._tmpl_attrib_table = QTableWidget(0, 5)
        self._tmpl_attrib_table.setSelectionBehavior(QTableWidget.SelectRows)
        self._tmpl_attrib_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self._tmpl_attrib_table.itemChanged.connect(self._on_tmpl_attrib_changed)
        self._tmpl_attrib_status = QLabel()
        self._tmpl_attrib_status.setStyleSheet("color: gray;")
        attr_lay.addWidget(self._tmpl_attrib_table)
        attr_lay.addWidget(self._tmpl_attrib_status)
        blocks_splitter.addWidget(self._grp_tmpl_attribs)

        blocks_splitter.setSizes([220, 650])
        layout.addWidget(blocks_splitter, 3)

        # ── Template I/O List ─────────────────────────────────────────────────
        self._grp_tmpl_ios = QGroupBox()
        ios_lay = QVBoxLayout(self._grp_tmpl_ios)

        ios_header = QWidget()
        ios_h_lay = QHBoxLayout(ios_header)
        ios_h_lay.setContentsMargins(0, 0, 0, 0)
        self._btn_add_tmpl_io    = QPushButton()
        self._btn_edit_tmpl_io   = QPushButton()
        self._btn_remove_tmpl_io = QPushButton()
        self._btn_add_tmpl_io.clicked.connect(self._add_template_io)
        self._btn_edit_tmpl_io.clicked.connect(self._edit_template_io)
        self._btn_remove_tmpl_io.clicked.connect(self._remove_template_io)
        for btn in (self._btn_add_tmpl_io, self._btn_edit_tmpl_io, self._btn_remove_tmpl_io):
            ios_h_lay.addWidget(btn)
        ios_h_lay.addStretch()
        ios_lay.addWidget(ios_header)

        self._tmpl_io_table = QTableWidget(0, len(_TMPL_IO_COLS))
        for i, w in enumerate(_TMPL_IO_WIDTHS):
            self._tmpl_io_table.setColumnWidth(i, w)
        self._tmpl_io_table.horizontalHeader().setStretchLastSection(True)
        self._tmpl_io_table.setSelectionBehavior(QTableWidget.SelectRows)
        self._tmpl_io_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self._tmpl_io_table.doubleClicked.connect(self._edit_template_io)
        ios_lay.addWidget(self._tmpl_io_table)
        layout.addWidget(self._grp_tmpl_ios, 2)

        # Initial placeholder
        self._tmpl_preview_lbl.set_text(tr("lbl_no_template_selected"))
        self._tmpl_attrib_status.setText(tr("lbl_no_template_selected"))

        return widget

    # ── Circuits tab ──────────────────────────────────────────────────────────

    def _build_circuits_tab(self) -> QWidget:
        widget = QWidget()
        outer = QVBoxLayout(widget)
        outer.setContentsMargins(6, 6, 6, 6)

        splitter = QSplitter(Qt.Vertical)

        # ── Top: Global circuit library ───────────────────────────────────────
        lib_widget = QWidget()
        lib_lay = QVBoxLayout(lib_widget)
        lib_lay.setContentsMargins(0, 0, 0, 0)

        lib_header = QWidget()
        lh_lay = QHBoxLayout(lib_header)
        lh_lay.setContentsMargins(0, 0, 0, 0)
        self._lbl_library_hdr = QLabel()
        self._lbl_library_hdr.setFont(QFont("", 10, QFont.Bold))
        lh_lay.addWidget(self._lbl_library_hdr)
        lh_lay.addStretch()
        self._btn_add_lib_circuit    = QPushButton()
        self._btn_edit_lib_circuit   = QPushButton()
        self._btn_remove_lib_circuit = QPushButton()
        self._btn_add_lib_circuit.clicked.connect(self._add_library_circuit)
        self._btn_edit_lib_circuit.clicked.connect(self._edit_library_circuit)
        self._btn_remove_lib_circuit.clicked.connect(self._remove_library_circuit)
        for btn in (self._btn_add_lib_circuit, self._btn_edit_lib_circuit,
                    self._btn_remove_lib_circuit):
            lh_lay.addWidget(btn)
        lib_lay.addWidget(lib_header)

        self._library_circuit_table = QTableWidget(0, 5)
        self._library_circuit_table.setSelectionBehavior(QTableWidget.SelectRows)
        self._library_circuit_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self._library_circuit_table.horizontalHeader().setStretchLastSection(True)
        self._library_circuit_table.doubleClicked.connect(self._edit_library_circuit)
        lib_lay.addWidget(self._library_circuit_table)
        splitter.addWidget(lib_widget)

        # ── Bottom: Project circuits ──────────────────────────────────────────
        proj_widget = QWidget()
        proj_lay = QVBoxLayout(proj_widget)
        proj_lay.setContentsMargins(0, 0, 0, 0)

        proj_header = QWidget()
        ph_lay = QHBoxLayout(proj_header)
        ph_lay.setContentsMargins(0, 0, 0, 0)
        self._lbl_project_circuits_hdr = QLabel()
        self._lbl_project_circuits_hdr.setFont(QFont("", 10, QFont.Bold))
        ph_lay.addWidget(self._lbl_project_circuits_hdr)
        ph_lay.addStretch()
        self._btn_add_to_project          = QPushButton()
        self._btn_remove_project_circuit  = QPushButton()
        self._btn_project_circuit_up      = QPushButton()
        self._btn_project_circuit_down    = QPushButton()
        self._btn_add_to_project.clicked.connect(self._add_circuit_to_project)
        self._btn_remove_project_circuit.clicked.connect(self._remove_circuit_from_project)
        self._btn_project_circuit_up.clicked.connect(self._project_circuit_up)
        self._btn_project_circuit_down.clicked.connect(self._project_circuit_down)
        for btn in (self._btn_add_to_project, self._btn_remove_project_circuit,
                    self._btn_project_circuit_up, self._btn_project_circuit_down):
            ph_lay.addWidget(btn)
        proj_lay.addWidget(proj_header)

        self._project_circuit_table = QTableWidget(0, 5)
        self._project_circuit_table.setSelectionBehavior(QTableWidget.SelectRows)
        self._project_circuit_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self._project_circuit_table.horizontalHeader().setStretchLastSection(True)
        proj_lay.addWidget(self._project_circuit_table)
        splitter.addWidget(proj_widget)

        splitter.setSizes([300, 300])
        outer.addWidget(splitter)
        return widget

    # ── Rules tab ─────────────────────────────────────────────────────────────

    def _build_rules_tab(self) -> QWidget:
        widget = QWidget()
        outer = QVBoxLayout(widget)
        outer.setContentsMargins(6, 6, 6, 6)

        # Header row with buttons
        header = QWidget()
        h_lay = QHBoxLayout(header)
        h_lay.setContentsMargins(0, 0, 0, 0)
        self._lbl_rules_hdr = QLabel()
        self._lbl_rules_hdr.setFont(QFont("", 10, QFont.Bold))
        h_lay.addWidget(self._lbl_rules_hdr)
        h_lay.addStretch()
        self._btn_add_rule    = QPushButton()
        self._btn_edit_rule   = QPushButton()
        self._btn_remove_rule = QPushButton()
        self._btn_rule_up     = QPushButton()
        self._btn_rule_down   = QPushButton()
        self._btn_add_rule.clicked.connect(self._add_rule)
        self._btn_edit_rule.clicked.connect(self._edit_rule)
        self._btn_remove_rule.clicked.connect(self._remove_rule)
        self._btn_rule_up.clicked.connect(self._rule_up)
        self._btn_rule_down.clicked.connect(self._rule_down)
        for btn in (self._btn_add_rule, self._btn_edit_rule, self._btn_remove_rule,
                    self._btn_rule_up, self._btn_rule_down):
            h_lay.addWidget(btn)
        outer.addWidget(header)

        # Table: Name | Description
        self._rules_table = QTableWidget(0, 2)
        self._rules_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self._rules_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self._rules_table.setSelectionBehavior(QTableWidget.SelectRows)
        self._rules_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self._rules_table.doubleClicked.connect(self._edit_rule)
        outer.addWidget(self._rules_table)
        return widget

    # ── Modules tab ───────────────────────────────────────────────────────────

    def _build_modules_tab(self) -> QWidget:
        widget = QWidget()
        outer = QVBoxLayout(widget)
        outer.setContentsMargins(6, 6, 6, 6)

        header = QWidget()
        h_lay = QHBoxLayout(header)
        h_lay.setContentsMargins(0, 0, 0, 0)
        self._lbl_modules_hdr = QLabel()
        self._lbl_modules_hdr.setFont(QFont("", 10, QFont.Bold))
        h_lay.addWidget(self._lbl_modules_hdr)
        h_lay.addStretch()
        self._btn_add_module       = QPushButton()
        self._btn_edit_module      = QPushButton()
        self._btn_remove_module    = QPushButton()
        self._btn_module_up        = QPushButton()
        self._btn_module_down      = QPushButton()
        self._btn_manage_io_values = QPushButton()
        self._btn_add_module.clicked.connect(self._add_module)
        self._btn_edit_module.clicked.connect(self._edit_module)
        self._btn_remove_module.clicked.connect(self._remove_module)
        self._btn_module_up.clicked.connect(self._module_up)
        self._btn_module_down.clicked.connect(self._module_down)
        self._btn_manage_io_values.clicked.connect(self._manage_io_values)
        for btn in (self._btn_add_module, self._btn_edit_module, self._btn_remove_module,
                    self._btn_module_up, self._btn_module_down, self._btn_manage_io_values):
            h_lay.addWidget(btn)
        outer.addWidget(header)

        # Table: # | Name | Company | Description | Other I/Os
        self._modules_table = QTableWidget(0, 5)
        self._modules_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self._modules_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self._modules_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self._modules_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.Stretch)
        self._modules_table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeToContents)
        self._modules_table.setSelectionBehavior(QTableWidget.SelectRows)
        self._modules_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self._modules_table.doubleClicked.connect(self._edit_module)
        outer.addWidget(self._modules_table)
        return widget

    # ── Modules CRUD ──────────────────────────────────────────────────────────

    def _load_modules(self):
        self._modules = mm.load_modules()
        self._module_io_values = mm.load_io_values()
        self._refresh_modules_table()

    # ── IO Types tab ──────────────────────────────────────────────────────────

    def _build_io_types_tab(self) -> QWidget:
        widget = QWidget()
        outer = QVBoxLayout(widget)
        outer.setContentsMargins(6, 6, 6, 6)

        header = QWidget()
        h_lay = QHBoxLayout(header)
        h_lay.setContentsMargins(0, 0, 0, 0)
        self._lbl_io_types_hdr = QLabel()
        self._lbl_io_types_hdr.setFont(QFont("", 10, QFont.Bold))
        h_lay.addWidget(self._lbl_io_types_hdr)
        h_lay.addStretch()
        self._btn_add_io_type    = QPushButton()
        self._btn_edit_io_type   = QPushButton()
        self._btn_remove_io_type = QPushButton()
        self._btn_add_io_type.clicked.connect(self._add_io_type)
        self._btn_edit_io_type.clicked.connect(self._edit_io_type)
        self._btn_remove_io_type.clicked.connect(self._remove_io_type)
        for btn in (self._btn_add_io_type, self._btn_edit_io_type, self._btn_remove_io_type):
            h_lay.addWidget(btn)
        outer.addWidget(header)

        # Columns: Name | Description | Signal Category | Direction | IO Template | Shared | Shared Template
        self._io_types_table = QTableWidget(0, 7)
        self._io_types_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self._io_types_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self._io_types_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self._io_types_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self._io_types_table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeToContents)
        self._io_types_table.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeToContents)
        self._io_types_table.horizontalHeader().setSectionResizeMode(6, QHeaderView.ResizeToContents)
        self._io_types_table.setSelectionBehavior(QTableWidget.SelectRows)
        self._io_types_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self._io_types_table.doubleClicked.connect(self._edit_io_type)
        outer.addWidget(self._io_types_table)
        return widget

    def _load_io_types(self):
        path = Path(__file__).parent / "io_types_library.json"
        try:
            if path.exists():
                self._io_types = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            self._io_types = []
        self._refresh_io_types_table()

    def _save_io_types(self):
        path = Path(__file__).parent / "io_types_library.json"
        path.write_text(json.dumps(self._io_types, indent=2, ensure_ascii=False), encoding="utf-8")

    def _refresh_io_types_table(self):
        self._io_types_table.setRowCount(0)
        for entry in self._io_types:
            row = self._io_types_table.rowCount()
            self._io_types_table.insertRow(row)
            shared = entry.get("shared", False)
            for col, val in enumerate([
                entry.get("name", ""),
                entry.get("description", ""),
                entry.get("signal_category", ""),
                entry.get("direction", ""),
                entry.get("io_template", ""),
                tr("opt_yes") if shared else "",
                entry.get("shared_template", "") if shared else "",
            ]):
                self._io_types_table.setItem(row, col, QTableWidgetItem(val))

    def _io_template_names(self) -> list[str]:
        """Return the list of available IO template names."""
        return self._io_template_mgr.list_templates()

    def _add_io_type(self):
        dlg = IOTypeDialog(self, io_templates=self._io_template_names())
        if dlg.exec() == QDialog.Accepted and dlg.result_data:
            self._io_types.append(dlg.result_data)
            self._refresh_io_types_table()
            self._save_io_types()

    def _edit_io_type(self):
        idx = self._io_types_table.currentRow()
        if idx < 0:
            return
        dlg = IOTypeDialog(self, data=self._io_types[idx],
                           io_templates=self._io_template_names())
        if dlg.exec() == QDialog.Accepted and dlg.result_data:
            self._io_types[idx] = dlg.result_data
            self._refresh_io_types_table()
            self._save_io_types()

    def _remove_io_type(self):
        idx = self._io_types_table.currentRow()
        if idx < 0:
            return
        name = self._io_types[idx].get("name", "")
        if QMessageBox.question(
            self, tr("msg_remove_io_type_title"), tr("msg_remove_io_type", name=name)
        ) == QMessageBox.Yes:
            self._io_types.pop(idx)
            self._refresh_io_types_table()
            self._save_io_types()

    def _save_modules(self):
        mm.save_modules(self._modules)

    def _refresh_modules_table(self):
        self._modules_table.setRowCount(0)
        # Keep current selection in the settings combobox
        prev_module = self._module_cb.currentText()
        self._module_cb.clear()
        self._module_cb.addItem("")  # blank = none selected
        for i, mod in enumerate(self._modules):
            row = self._modules_table.rowCount()
            self._modules_table.insertRow(row)
            for col, val in enumerate([
                str(i + 1),
                mod.get("name", ""),
                mod.get("company", ""),
                mod.get("description", ""),
                str(len(mod.get("other_ios", []))),
            ]):
                self._modules_table.setItem(row, col, QTableWidgetItem(val))
        # Repopulate combobox items (names only)
        for mod in self._modules:
            name = mod.get("name", "")
            if name:
                self._module_cb.addItem(name)
        # Restore previous selection if still present
        idx = self._module_cb.findText(prev_module)
        self._module_cb.setCurrentIndex(idx if idx >= 0 else 0)
        self._refresh_io_summary()

    def _module_template_names(self) -> list[str]:
        """Return controller template names for module assignment."""
        return self._ctrl_template_mgr.list_templates()

    def _add_module(self):
        dlg = ModuleDialog(self, io_values=self._module_io_values, templates=self._module_template_names())
        if dlg.exec() == QDialog.Accepted and dlg.result_data:
            self._modules.append(dlg.result_data)
            self._refresh_modules_table()
            self._save_modules()

    def _edit_module(self):
        idx = self._modules_table.currentRow()
        if idx < 0:
            return
        dlg = ModuleDialog(self, self._modules[idx], io_values=self._module_io_values,
                           templates=self._module_template_names())
        if dlg.exec() == QDialog.Accepted and dlg.result_data:
            self._modules[idx] = dlg.result_data
            self._refresh_modules_table()
            self._save_modules()

    def _remove_module(self):
        idx = self._modules_table.currentRow()
        if idx < 0:
            return
        name = self._modules[idx].get("name", "")
        if QMessageBox.question(
            self, tr("msg_remove_module_title"), tr("msg_remove_module", name=name)
        ) == QMessageBox.Yes:
            self._modules.pop(idx)
            self._refresh_modules_table()
            self._save_modules()

    def _module_up(self):
        idx = self._modules_table.currentRow()
        if idx > 0:
            self._modules[idx - 1], self._modules[idx] = self._modules[idx], self._modules[idx - 1]
            self._refresh_modules_table()
            self._modules_table.selectRow(idx - 1)
            self._save_modules()

    def _module_down(self):
        idx = self._modules_table.currentRow()
        if 0 <= idx < len(self._modules) - 1:
            self._modules[idx + 1], self._modules[idx] = self._modules[idx], self._modules[idx + 1]
            self._refresh_modules_table()
            self._modules_table.selectRow(idx + 1)
            self._save_modules()

    def _manage_io_values(self):
        dlg = IOValuesDialog(self, self._module_io_values)
        if dlg.exec() == QDialog.Accepted and dlg.result_values is not None:
            self._module_io_values = dlg.result_values
            mm.save_io_values(self._module_io_values)

    # ── Rules CRUD ────────────────────────────────────────────────────────────

    def _load_rules(self):
        self._rules = rl.load_rules()
        self._refresh_rules_table()

    def _save_rules(self):
        rl.save_rules(self._rules)

    def _refresh_rules_table(self):
        self._rules_table.setRowCount(0)
        for rule in self._rules:
            row = self._rules_table.rowCount()
            self._rules_table.insertRow(row)
            for col, val in enumerate([rule.get("name", ""), rule.get("description", "")]):
                self._rules_table.setItem(row, col, QTableWidgetItem(val))

    def _add_rule(self):
        dlg = RuleDialog(self)
        if dlg.exec() == QDialog.Accepted and dlg.result_data:
            self._rules.append(dlg.result_data)
            self._refresh_rules_table()
            self._save_rules()

    def _edit_rule(self):
        idx = self._rules_table.currentRow()
        if idx < 0:
            return
        dlg = RuleDialog(self, self._rules[idx])
        if dlg.exec() == QDialog.Accepted and dlg.result_data:
            self._rules[idx] = dlg.result_data
            self._refresh_rules_table()
            self._save_rules()

    def _remove_rule(self):
        idx = self._rules_table.currentRow()
        if idx < 0:
            return
        name = self._rules[idx].get("name", "")
        if QMessageBox.question(
            self, tr("msg_remove_rule_title"), tr("msg_remove_rule", name=name)
        ) == QMessageBox.Yes:
            self._rules.pop(idx)
            self._refresh_rules_table()
            self._save_rules()

    def _rule_up(self):
        idx = self._rules_table.currentRow()
        if idx > 0:
            self._rules[idx - 1], self._rules[idx] = self._rules[idx], self._rules[idx - 1]
            self._refresh_rules_table()
            self._rules_table.selectRow(idx - 1)
            self._save_rules()

    def _rule_down(self):
        idx = self._rules_table.currentRow()
        if 0 <= idx < len(self._rules) - 1:
            self._rules[idx + 1], self._rules[idx] = self._rules[idx], self._rules[idx + 1]
            self._refresh_rules_table()
            self._rules_table.selectRow(idx + 1)
            self._save_rules()

    # ── Valves tab builder ────────────────────────────────────────────────────

    def _build_valves_tab(self) -> QWidget:
        widget = QWidget()
        outer = QVBoxLayout(widget)
        outer.setContentsMargins(6, 6, 6, 6)

        splitter = QSplitter(Qt.Vertical)

        # ── Top: Valve type config (global) ───────────────────────────────────
        top = QWidget()
        top_lay = QHBoxLayout(top)
        top_lay.setContentsMargins(0, 0, 0, 0)

        # Left: type list
        type_panel = QWidget()
        type_lay = QVBoxLayout(type_panel)
        type_lay.setContentsMargins(0, 0, 0, 0)
        self._lbl_valve_type_hdr = QLabel()
        self._lbl_valve_type_hdr.setFont(QFont("", 10, QFont.Bold))
        type_lay.addWidget(self._lbl_valve_type_hdr)
        self._valve_type_list = QListWidget()
        self._valve_type_list.currentRowChanged.connect(self._on_valve_type_selected)
        type_lay.addWidget(self._valve_type_list, 1)
        self._btn_add_valve_type    = QPushButton()
        self._btn_rename_valve_type = QPushButton()
        self._btn_remove_valve_type = QPushButton()
        self._btn_add_valve_type.clicked.connect(self._add_valve_type)
        self._btn_rename_valve_type.clicked.connect(self._rename_valve_type)
        self._btn_remove_valve_type.clicked.connect(self._remove_valve_type)
        type_lay.addWidget(_make_toolbar_row(
            ("", self._add_valve_type),
            ("", self._rename_valve_type),
            ("", self._remove_valve_type),
        ))
        # replace the generic toolbar row with individually-labelled buttons
        type_lay.itemAt(type_lay.count() - 1).widget().deleteLater()
        btn_row_t = QWidget()
        btn_row_t_lay = QHBoxLayout(btn_row_t)
        btn_row_t_lay.setContentsMargins(0, 0, 0, 0)
        for btn in (self._btn_add_valve_type, self._btn_rename_valve_type,
                    self._btn_remove_valve_type):
            btn_row_t_lay.addWidget(btn)
        btn_row_t_lay.addStretch()
        type_lay.addWidget(btn_row_t)
        top_lay.addWidget(type_panel, 1)

        # Right: IOs for selected type
        io_panel = QWidget()
        io_lay = QVBoxLayout(io_panel)
        io_lay.setContentsMargins(0, 0, 0, 0)
        self._lbl_valve_ios_hdr = QLabel()
        self._lbl_valve_ios_hdr.setFont(QFont("", 10, QFont.Bold))
        io_lay.addWidget(self._lbl_valve_ios_hdr)
        self._valve_io_table = QTableWidget(0, 5)
        self._valve_io_table.setSelectionBehavior(QTableWidget.SelectRows)
        self._valve_io_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self._valve_io_table.horizontalHeader().setStretchLastSection(True)
        self._valve_io_table.doubleClicked.connect(self._edit_valve_io)
        io_lay.addWidget(self._valve_io_table, 1)
        self._btn_add_valve_io    = QPushButton()
        self._btn_edit_valve_io   = QPushButton()
        self._btn_remove_valve_io = QPushButton()
        self._btn_add_valve_io.clicked.connect(self._add_valve_io)
        self._btn_edit_valve_io.clicked.connect(self._edit_valve_io)
        self._btn_remove_valve_io.clicked.connect(self._remove_valve_io)
        btn_row_io = QWidget()
        btn_row_io_lay = QHBoxLayout(btn_row_io)
        btn_row_io_lay.setContentsMargins(0, 0, 0, 0)
        for btn in (self._btn_add_valve_io, self._btn_edit_valve_io,
                    self._btn_remove_valve_io):
            btn_row_io_lay.addWidget(btn)
        btn_row_io_lay.addStretch()
        io_lay.addWidget(btn_row_io)
        top_lay.addWidget(io_panel, 2)

        splitter.addWidget(top)

        # ── Bottom: Valves per circuit ─────────────────────────────────────────
        bot = QWidget()
        bot_lay = QVBoxLayout(bot)
        bot_lay.setContentsMargins(0, 0, 0, 0)
        self._lbl_project_valves_hdr = QLabel()
        self._lbl_project_valves_hdr.setFont(QFont("", 10, QFont.Bold))
        bot_lay.addWidget(self._lbl_project_valves_hdr)
        # global template + quantity row
        tmpl_row = QWidget()
        tmpl_row_lay = QHBoxLayout(tmpl_row)
        tmpl_row_lay.setContentsMargins(0, 0, 0, 0)
        self._lbl_valve_template = QLabel()
        self._valve_template_cb = QComboBox()
        self._valve_template_cb.addItem("")
        self._valve_template_cb.currentIndexChanged.connect(self._on_valve_template_changed)
        self._lbl_valve_qty = QLabel()
        self._valve_qty_sb = QSpinBox()
        self._valve_qty_sb.setMinimum(1)
        self._valve_qty_sb.setMaximum(9999)
        self._valve_qty_sb.valueChanged.connect(self._on_valve_qty_changed)
        tmpl_row_lay.addWidget(self._lbl_valve_template)
        tmpl_row_lay.addWidget(self._valve_template_cb, 2)
        tmpl_row_lay.addSpacing(12)
        tmpl_row_lay.addWidget(self._lbl_valve_qty)
        tmpl_row_lay.addWidget(self._valve_qty_sb)
        tmpl_row_lay.addStretch()
        bot_lay.addWidget(tmpl_row)
        # circuit selector row
        circuit_row = QWidget()
        circuit_row_lay = QHBoxLayout(circuit_row)
        circuit_row_lay.setContentsMargins(0, 0, 0, 0)
        self._lbl_select_circuit = QLabel()
        self._valve_circuit_cb = QComboBox()
        self._valve_circuit_cb.currentIndexChanged.connect(self._refresh_valve_table)
        circuit_row_lay.addWidget(self._lbl_select_circuit)
        circuit_row_lay.addWidget(self._valve_circuit_cb, 1)
        bot_lay.addWidget(circuit_row)
        self._valve_table = QTableWidget(0, 4)
        self._valve_table.setSelectionBehavior(QTableWidget.SelectRows)
        self._valve_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self._valve_table.horizontalHeader().setStretchLastSection(True)
        self._valve_table.doubleClicked.connect(self._edit_valve)
        bot_lay.addWidget(self._valve_table, 1)
        self._btn_add_valve    = QPushButton()
        self._btn_edit_valve   = QPushButton()
        self._btn_remove_valve = QPushButton()
        self._btn_add_valve.clicked.connect(self._add_valve)
        self._btn_edit_valve.clicked.connect(self._edit_valve)
        self._btn_remove_valve.clicked.connect(self._remove_valve)
        btn_row_v = QWidget()
        btn_row_v_lay = QHBoxLayout(btn_row_v)
        btn_row_v_lay.setContentsMargins(0, 0, 0, 0)
        for btn in (self._btn_add_valve, self._btn_edit_valve, self._btn_remove_valve):
            btn_row_v_lay.addWidget(btn)
        btn_row_v_lay.addStretch()
        bot_lay.addWidget(btn_row_v)
        splitter.addWidget(bot)

        outer.addWidget(splitter)
        return widget

    # ── Valves CRUD ───────────────────────────────────────────────────────────

    def _load_valve_config(self):
        self._valve_types = vm.load_valve_types()
        self._refresh_valve_type_list()
        self._refresh_valve_circuit_combo()
        # populate global template combo
        self._valve_template_cb.blockSignals(True)
        self._valve_template_cb.clear()
        self._valve_template_cb.addItem("")
        self._valve_template_cb.addItems(self._template_mgr.list_templates())
        cfg = vm.load_valve_config()
        tmpl_idx = self._valve_template_cb.findText(cfg.get("template", ""))
        self._valve_template_cb.setCurrentIndex(max(tmpl_idx, 0))
        self._valve_qty_sb.blockSignals(True)
        self._valve_qty_sb.setValue(int(cfg.get("quantity", 1)))
        self._valve_qty_sb.blockSignals(False)
        self._valve_template_cb.blockSignals(False)

    def _refresh_valve_circuit_combo(self):
        """Repopulate the circuit filter combo (with an ‘All’ option at top)."""
        prev = self._valve_circuit_cb.currentText()
        self._valve_circuit_cb.blockSignals(True)
        self._valve_circuit_cb.clear()
        self._valve_circuit_cb.addItem(tr("opt_all_circuits"))
        for c in self._library_circuits:
            self._valve_circuit_cb.addItem(c.name)
        idx = self._valve_circuit_cb.findText(prev)
        self._valve_circuit_cb.setCurrentIndex(max(0, idx))
        self._valve_circuit_cb.blockSignals(False)
        self._refresh_valve_table()

    def _filter_circuit_name(self) -> str | None:
        """Return the selected circuit name filter, or None for ‘All’."""
        idx = self._valve_circuit_cb.currentIndex()
        if idx <= 0:
            return None
        # index 0 = All, index 1+ maps to library_circuits[idx-1]
        lib_idx = idx - 1
        if 0 <= lib_idx < len(self._library_circuits):
            return self._library_circuits[lib_idx].name
        return None

    def _refresh_valve_type_list(self):
        self._valve_type_list.clear()
        for t in self._valve_types:
            self._valve_type_list.addItem(t)
        self._refresh_valve_io_table()

    def _on_valve_type_selected(self, _row: int):
        self._refresh_valve_io_table()

    def _current_valve_type(self) -> str | None:
        row = self._valve_type_list.currentRow()
        if 0 <= row < len(self._valve_types):
            return self._valve_types[row]
        return None

    def _refresh_valve_io_table(self):
        self._valve_io_table.setRowCount(0)
        vtype = self._current_valve_type()
        if vtype is None:
            return
        ios = vm.get_ios_for_type(vtype)
        for io in ios:
            row = self._valve_io_table.rowCount()
            self._valve_io_table.insertRow(row)
            for col, val in enumerate([
                io.name, io.description, io.signal_type, io.direction, io.io_type,
            ]):
                self._valve_io_table.setItem(row, col, QTableWidgetItem(val))

    def _add_valve_type(self):
        name, ok = QInputDialog.getText(
            self, tr("dlg_valve_type_name_title"), tr("dlg_valve_type_name_prompt")
        )
        name = name.strip()
        if not ok or not name:
            return
        if name in self._valve_types:
            QMessageBox.warning(self, tr("msg_validation"),
                                tr("msg_valve_type_exists", name=name))
            return
        self._valve_types.append(name)
        vm.save_valve_types(self._valve_types)
        self._refresh_valve_type_list()
        self._valve_type_list.setCurrentRow(len(self._valve_types) - 1)

    def _rename_valve_type(self):
        old = self._current_valve_type()
        if old is None:
            QMessageBox.information(self, tr("tab_valves"), tr("msg_select_valve_type"))
            return
        new_name, ok = QInputDialog.getText(
            self, tr("dlg_valve_type_name_title"),
            tr("dlg_valve_type_rename_prompt", name=old),
            text=old,
        )
        new_name = new_name.strip()
        if not ok or not new_name or new_name == old:
            return
        if new_name in self._valve_types:
            QMessageBox.warning(self, tr("msg_validation"),
                                tr("msg_valve_type_exists", name=new_name))
            return
        row = self._valve_types.index(old)
        vm.rename_type(old, new_name)
        self._valve_types[row] = new_name
        # update any circuit valves that referenced the old type
        for c in self._library_circuits:
            for v in c.valves:
                if v.valve_type == old:
                    v.valve_type = new_name
        self._save_library()
        self._refresh_valve_type_list()
        self._valve_type_list.setCurrentRow(row)
        self._refresh_valve_table()

    def _remove_valve_type(self):
        vtype = self._current_valve_type()
        if vtype is None:
            QMessageBox.information(self, tr("tab_valves"), tr("msg_select_valve_type"))
            return
        if QMessageBox.question(
            self, tr("msg_remove_valve_type_title"),
            tr("msg_remove_valve_type", name=vtype),
        ) == QMessageBox.Yes:
            vm.delete_type(vtype)
            self._valve_types.remove(vtype)
            self._refresh_valve_type_list()

    def _add_valve_io(self):
        vtype = self._current_valve_type()
        if vtype is None:
            QMessageBox.information(self, tr("tab_valves"), tr("msg_select_valve_type"))
            return
        dlg = ValveIODialog(self, io_types=self._io_types)
        if dlg.exec() == QDialog.Accepted and dlg.result_data:
            from models import ValveIO
            ios = vm.get_ios_for_type(vtype)
            ios.append(ValveIO(**dlg.result_data))
            vm.set_ios_for_type(vtype, ios)
            self._refresh_valve_io_table()

    def _edit_valve_io(self):
        vtype = self._current_valve_type()
        if vtype is None:
            return
        idx = self._valve_io_table.currentRow()
        if idx < 0:
            return
        ios = vm.get_ios_for_type(vtype)
        from dataclasses import asdict
        dlg = ValveIODialog(self, data=asdict(ios[idx]), io_types=self._io_types)
        if dlg.exec() == QDialog.Accepted and dlg.result_data:
            from models import ValveIO
            ios[idx] = ValveIO(**dlg.result_data)
            vm.set_ios_for_type(vtype, ios)
            self._refresh_valve_io_table()

    def _remove_valve_io(self):
        vtype = self._current_valve_type()
        if vtype is None:
            return
        idx = self._valve_io_table.currentRow()
        if idx < 0:
            return
        ios = vm.get_ios_for_type(vtype)
        ios.pop(idx)
        vm.set_ios_for_type(vtype, ios)
        self._refresh_valve_io_table()

    def _refresh_valve_table(self):
        """Rebuild the valve table, optionally filtered by circuit."""
        self._valve_table.setRowCount(0)
        self._valve_rows: list[tuple[int, int]] = []  # (circuit_idx, valve_idx)
        filter_name = self._filter_circuit_name()
        for ci, circuit in enumerate(self._library_circuits):
            if filter_name is not None and circuit.name != filter_name:
                continue
            for vi, v in enumerate(circuit.valves):
                row = self._valve_table.rowCount()
                self._valve_table.insertRow(row)
                for col, val in enumerate([v.tag, v.valve_type, v.description, circuit.name]):
                    self._valve_table.setItem(row, col, QTableWidgetItem(val))
                self._valve_rows.append((ci, vi))

    def _valve_row_owners(self, row: int):
        """Return (circuit, valve_idx) for table *row*, or (None, -1)."""
        if 0 <= row < len(self._valve_rows):
            ci, vi = self._valve_rows[row]
            return self._library_circuits[ci], vi
        return None, -1

    def _save_valve_global_config(self):
        vm.save_valve_config({
            "template": self._valve_template_cb.currentText(),
            "quantity": self._valve_qty_sb.value(),
        })

    def _on_valve_template_changed(self):
        self._save_valve_global_config()

    def _on_valve_qty_changed(self):
        self._save_valve_global_config()

    def _next_valve_id(self) -> str:
        """Return the next auto-generated valve ID (V001, V002, …)."""
        existing = {
            v.tag
            for c in self._library_circuits
            for v in c.valves
        }
        n = 1
        while True:
            candidate = f"V{n:03d}"
            if candidate not in existing:
                return candidate
            n += 1

    def _add_valve(self):
        if not self._valve_types:
            QMessageBox.information(self, tr("tab_valves"), tr("msg_no_valve_types"))
            return
        if not self._library_circuits:
            QMessageBox.information(self, tr("tab_valves"), tr("msg_select_circuit"))
            return
        locked = self._filter_circuit_name()   # pre-select if filtered
        circuit_names = [c.name for c in self._library_circuits]
        dlg = ValveDialog(self, valve_types=self._valve_types,
                          circuits=circuit_names, circuit_locked=locked)
        if dlg.exec() == QDialog.Accepted and dlg.result_data:
            cname = dlg.result_data.pop("circuit_name", "")
            target = next((c for c in self._library_circuits if c.name == cname), None)
            if target is None and self._library_circuits:
                target = self._library_circuits[0]
            if target is not None:
                auto_id = self._next_valve_id()
                dlg.result_data["tag"] = auto_id
                dlg.result_data["circuit_name"] = target.name
                target.valves.append(Valve(**dlg.result_data))
                self._save_library()
                self._refresh_valve_table()

    def _edit_valve(self):
        idx = self._valve_table.currentRow()
        if idx < 0:
            return
        circuit, vi = self._valve_row_owners(idx)
        if circuit is None:
            return
        from dataclasses import asdict
        circuit_names = [c.name for c in self._library_circuits]
        d = asdict(circuit.valves[vi])
        d["circuit_name"] = circuit.name
        dlg = ValveDialog(self, valve_types=self._valve_types,
                          circuits=circuit_names, data=d)
        if dlg.exec() == QDialog.Accepted and dlg.result_data:
            new_cname = dlg.result_data.pop("circuit_name", circuit.name)
            new_circuit = next((c for c in self._library_circuits if c.name == new_cname),
                               circuit)
            # preserve the existing auto-generated ID
            dlg.result_data["tag"] = circuit.valves[vi].tag
            dlg.result_data["circuit_name"] = new_circuit.name
            if new_circuit is circuit:
                circuit.valves[vi] = Valve(**dlg.result_data)
            else:
                # moved to another circuit
                circuit.valves.pop(vi)
                new_circuit.valves.append(Valve(**dlg.result_data))
            self._save_library()
            self._refresh_valve_table()

    def _remove_valve(self):
        idx = self._valve_table.currentRow()
        if idx < 0:
            return
        circuit, vi = self._valve_row_owners(idx)
        if circuit is None:
            return
        tag = circuit.valves[vi].tag
        if QMessageBox.question(
            self, tr("msg_remove_valve_title"), tr("msg_remove_valve", tag=tag)
        ) == QMessageBox.Yes:
            circuit.valves.pop(vi)
            self._save_library()
            self._refresh_valve_table()

    # ── Circuit library CRUD ──────────────────────────────────────────────────

    def _load_library(self):
        """Load the global circuit library from disk and refresh the table."""
        self._library_circuits = [Circuit(**d) for d in cl.load_library()]
        self._refresh_library_table()
        self._refresh_valve_circuit_combo()

    def _save_library(self):
        """Persist the global circuit library to disk (no project dirty flag)."""
        cl.save_library(self._library_circuits)

    def _lookup_circuit(self, name: str) -> Circuit | None:
        """Return the library Circuit whose name matches *name*, or None."""
        for c in self._library_circuits:
            if c.name == name:
                return c
        return None

    def _refresh_library_table(self):
        self._library_circuit_table.setRowCount(0)
        for i, circuit in enumerate(self._library_circuits):
            row = self._library_circuit_table.rowCount()
            self._library_circuit_table.insertRow(row)
            for col, val in enumerate([
                str(i + 1),
                circuit.name,
                circuit.circuit_number,
                circuit.description,
                ", ".join(circuit.templates) if circuit.templates else "\u2014",
            ]):
                self._library_circuit_table.setItem(row, col, QTableWidgetItem(val))

    def _add_library_circuit(self):
        dlg = CircuitDialog(self, available_templates=self._template_mgr.list_templates())
        if dlg.exec() == QDialog.Accepted and dlg.result_circuit:
            self._library_circuits.append(dlg.result_circuit)
            self._refresh_library_table()
            self._save_library()
            self._refresh_valve_circuit_combo()

    def _edit_library_circuit(self):
        idx = self._library_circuit_table.currentRow()
        if idx < 0:
            return
        dlg = CircuitDialog(self,
                            available_templates=self._template_mgr.list_templates(),
                            data=self._library_circuits[idx])
        if dlg.exec() == QDialog.Accepted and dlg.result_circuit:
            # preserve existing valves when re-editing a circuit
            dlg.result_circuit.valves = self._library_circuits[idx].valves
            self._library_circuits[idx] = dlg.result_circuit
            self._refresh_library_table()
            self._refresh_project_circuits_table()   # names/info may have changed
            self._save_library()
            self._refresh_valve_circuit_combo()

    def _remove_library_circuit(self):
        idx = self._library_circuit_table.currentRow()
        if idx < 0:
            return
        name = self._library_circuits[idx].name
        if QMessageBox.question(
            self, tr("msg_remove_lib_circuit_title"),
            tr("msg_remove_lib_circuit", name=name)
        ) == QMessageBox.Yes:
            del self._library_circuits[idx]
            self._refresh_library_table()
            self._save_library()
            self._refresh_valve_circuit_combo()

    # ── Project circuits CRUD ─────────────────────────────────────────────────

    def _resolve_project_circuit_numbers(self) -> list[str]:
        """Return the effective circuit number for each project circuit ref.

        Circuits whose ``circuit_number`` is ``"#"`` are replaced by an
        auto-incrementing counter (1, 2, 3, …) based on their order of
        appearance in the project list.  Circuits with any other number keep
        their original value.
        """
        resolved: list[str] = []
        counter = 1
        for name in self._project_circuit_refs:
            circuit = self._lookup_circuit(name)
            if circuit is not None and circuit.circuit_number == "#":
                resolved.append(str(counter))
                counter += 1
            else:
                resolved.append(circuit.circuit_number if circuit else "")
        return resolved

    def _refresh_project_circuits_table(self):
        self._project_circuit_table.setRowCount(0)
        resolved_numbers = self._resolve_project_circuit_numbers()
        for i, name in enumerate(self._project_circuit_refs):
            circuit = self._lookup_circuit(name)
            row = self._project_circuit_table.rowCount()
            self._project_circuit_table.insertRow(row)
            for col, val in enumerate([
                str(i + 1),
                name,
                resolved_numbers[i],
                circuit.description    if circuit else "",
                (", ".join(circuit.templates) if circuit and circuit.templates else "\u2014"),
            ]):
                item = QTableWidgetItem(val)
                if circuit is None:
                    item.setForeground(self._project_circuit_table.palette().placeholderText())
                self._project_circuit_table.setItem(row, col, item)

    def _add_circuit_to_project(self):
        """Add the selected library circuit to the project list (duplicates allowed)."""
        idx = self._library_circuit_table.currentRow()
        if idx < 0:
            QMessageBox.information(self, tr("tab_circuits"),
                                    tr("msg_select_library_circuit"))
            return
        self._project_circuit_refs.append(self._library_circuits[idx].name)
        self._refresh_project_circuits_table()
        self._refresh_io_table()
        self._mark_dirty()

    def _remove_circuit_from_project(self):
        idx = self._project_circuit_table.currentRow()
        if idx < 0:
            return
        name = self._project_circuit_refs[idx]
        if QMessageBox.question(
            self, tr("msg_remove_project_circuit_title"),
            tr("msg_remove_project_circuit", name=name)
        ) == QMessageBox.Yes:
            del self._project_circuit_refs[idx]
            self._refresh_project_circuits_table()
            self._refresh_io_table()
            self._mark_dirty()

    def _project_circuit_up(self):
        idx = self._project_circuit_table.currentRow()
        if idx > 0:
            self._project_circuit_refs[idx - 1], self._project_circuit_refs[idx] = (
                self._project_circuit_refs[idx], self._project_circuit_refs[idx - 1]
            )
            self._refresh_project_circuits_table()
            self._project_circuit_table.selectRow(idx - 1)
            self._refresh_io_table()
            self._mark_dirty()

    def _project_circuit_down(self):
        idx = self._project_circuit_table.currentRow()
        if 0 <= idx < len(self._project_circuit_refs) - 1:
            self._project_circuit_refs[idx + 1], self._project_circuit_refs[idx] = (
                self._project_circuit_refs[idx], self._project_circuit_refs[idx + 1]
            )
            self._refresh_project_circuits_table()
            self._project_circuit_table.selectRow(idx + 1)
            self._refresh_io_table()
            self._mark_dirty()

    # ── I/O CRUD ──────────────────────────────────────────────────────────────

    def _refresh_io_summary(self):
        if not hasattr(self, "_lbl_io_summary"):
            return
        total_io = len(self._io_items)
        total_in  = sum(1 for io in self._io_items if io.io_type == "Input")
        total_out = total_io - total_in
        num_mod   = len(self._modules)
        self._lbl_io_summary.setText(
            f"{num_mod} module(s)  ·  {total_io} IO(s)  ({total_in} in / {total_out} out)"
        )

    def _refresh_io_table(self):
        self._io_table.setRowCount(0)
        self._io_items.clear()
        resolved_numbers = self._resolve_project_circuit_numbers()
        for ref_idx, circuit_name in enumerate(self._project_circuit_refs):
            circuit = self._lookup_circuit(circuit_name)
            if circuit is None:
                continue
            circuit_no = resolved_numbers[ref_idx]
            for tmpl_name in circuit.templates:
                ios = self._template_mgr.get_template_ios(tmpl_name)
                for io in ios:
                    io_name = io.get("name", "").replace("#", circuit_no)
                    io_desc = io.get("description", "").replace("#", circuit_no)
                    row = self._io_table.rowCount()
                    self._io_table.insertRow(row)
                    for col, val in enumerate([
                        circuit_name,
                        circuit_no,
                        tmpl_name,
                        io_name,
                        io_desc,
                        io.get("signal_type", ""),
                        io.get("direction", ""),
                        io.get("io_type", ""),
                    ]):
                        self._io_table.setItem(row, col, QTableWidgetItem(val))
                    self._io_items.append(IOItem(
                        tag=io_name,
                        io_type=io.get("direction", "Input"),
                        description=io_desc,
                        signal_type=io.get("signal_type", ""),
                        io_type_name=io.get("io_type", ""),
                    ))
        self._refresh_io_summary()

    def _add_io(self):
        dlg = IODialog(self)
        if dlg.exec() == QDialog.Accepted and dlg.result_data:
            self._io_items.append(IOItem(**dlg.result_data))
            self._refresh_io_table()
            self._mark_dirty()

    def _edit_io(self):
        idx = self._io_table.currentRow()
        if idx < 0:
            return
        item = self._io_items[idx]
        dlg = IODialog(self, {
            "io_type": item.io_type, "tag": item.tag, "address": item.address,
            "description": item.description, "panel": item.panel,
            "signal_type": item.signal_type, "terminal": item.terminal,
            "cable": item.cable, "notes": item.notes,
        })
        if dlg.exec() == QDialog.Accepted and dlg.result_data:
            self._io_items[idx] = IOItem(**dlg.result_data)
            self._refresh_io_table()
            self._mark_dirty()

    def _remove_io(self):
        idx = self._io_table.currentRow()
        if idx < 0:
            return
        tag = self._io_items[idx].tag
        if QMessageBox.question(self, tr("msg_remove_io_title"), tr("msg_remove_io", tag=tag)) == QMessageBox.Yes:
            self._io_items.pop(idx)
            self._refresh_io_table()
            self._mark_dirty()

    # ── Template I/O CRUD ─────────────────────────────────────────────────────

    def _refresh_tmpl_io_table(self):
        self._tmpl_io_table.setRowCount(0)
        for io in self._tmpl_ios:
            row = self._tmpl_io_table.rowCount()
            self._tmpl_io_table.insertRow(row)
            for col, val in enumerate([
                io.get("name", ""),
                io.get("description", ""),
                io.get("signal_type", ""),
                io.get("direction", ""),
                io.get("io_type", ""),
            ]):
                self._tmpl_io_table.setItem(row, col, QTableWidgetItem(val))

    def _save_tmpl_ios(self):
        if self._tmpl_current_name:
            self._active_template_mgr.set_template_ios(self._tmpl_current_name, self._tmpl_ios)
            self._refresh_io_table()

    def _add_template_io(self):
        if not self._tmpl_current_name:
            return
        dlg = TemplateIODialog(self, io_types=self._io_types)
        if dlg.exec() == QDialog.Accepted and dlg.result_data:
            self._tmpl_ios.append(dlg.result_data)
            self._refresh_tmpl_io_table()
            self._save_tmpl_ios()

    def _edit_template_io(self):
        if not self._tmpl_current_name:
            return
        idx = self._tmpl_io_table.currentRow()
        if idx < 0:
            return
        dlg = TemplateIODialog(self, self._tmpl_ios[idx], io_types=self._io_types)
        if dlg.exec() == QDialog.Accepted and dlg.result_data:
            self._tmpl_ios[idx] = dlg.result_data
            self._refresh_tmpl_io_table()
            self._save_tmpl_ios()

    def _remove_template_io(self):
        if not self._tmpl_current_name:
            return
        idx = self._tmpl_io_table.currentRow()
        if idx < 0:
            return
        name = self._tmpl_ios[idx].get("name", "")
        if QMessageBox.question(
            self, tr("msg_remove_template_io_title"),
            tr("msg_remove_template_io", name=name)
        ) == QMessageBox.Yes:
            self._tmpl_ios.pop(idx)
            self._refresh_tmpl_io_table()
            self._save_tmpl_ios()



    # ── Template management ───────────────────────────────────────────────────

    def _on_template_selected(self, current, previous):
        """Update the Template tab when the selected template changes."""
        if current is not None:
            # Deselect the controller template list without triggering its signal
            self._ctrl_tmpl_list.blockSignals(True)
            self._ctrl_tmpl_list.clearSelection()
            self._ctrl_tmpl_list.setCurrentRow(-1)
            self._ctrl_tmpl_list.blockSignals(False)
            # Deselect the IO template list without triggering its signal
            self._io_tmpl_list.blockSignals(True)
            self._io_tmpl_list.clearSelection()
            self._io_tmpl_list.setCurrentRow(-1)
            self._io_tmpl_list.blockSignals(False)

        self._tmpl_blocks = []
        self._tmpl_attr_values = {}
        self._tmpl_current_block = None
        self._tmpl_current_name = None
        self._tmpl_axis_bounds = None
        self._tmpl_block_list.clear()
        self._tmpl_attrib_table.blockSignals(True)
        self._tmpl_attrib_table.setRowCount(0)
        self._tmpl_attrib_table.blockSignals(False)
        self._tmpl_ios = []
        self._refresh_tmpl_io_table()

        if current is None:
            self._tmpl_preview_lbl.set_text(tr("lbl_no_template_selected"))
            self._tmpl_attrib_status.setText(tr("lbl_no_template_selected"))
            return

        name = current.text()
        self._tmpl_current_name = name
        self._active_template_mgr = self._template_mgr
        self._active_tmpl_type = "regular"
        self._update_tmpl_io_ui()

        # Start background preview render
        self._start_preview_render(name)

        # Load blocks
        self._tmpl_blocks = self._template_mgr.get_template_blocks(name)
        if self._tmpl_blocks:
            for blk in self._tmpl_blocks:
                self._tmpl_block_list.addItem(blk["name"])
            self._tmpl_block_list.setCurrentRow(0)
        else:
            self._tmpl_attrib_status.setText(tr("msg_no_blocks"))

        # Load template IOs
        self._tmpl_ios = self._template_mgr.get_template_ios(name)
        self._refresh_tmpl_io_table()

    def _start_preview_render(self, name: str, dpi_factor: float = 1.0, fit: bool = True):
        """Cancel any running preview and start a new background render.

        dpi_factor – render resolution multiplier (1.0 = 96 DPI baseline).
        fit        – True  → set_pixmap (fit-to-view on arrival).
                     False → update_pixmap_at_scale (preserve current zoom).
        """
        if self._preview_worker is not None:
            self._preview_worker.cancel()

        self._preview_generation += 1
        generation = self._preview_generation
        self._preview_fit_on_next = fit

        if fit:
            self._tmpl_preview_lbl.set_text(tr("msg_preview_loading"))

        worker = PreviewWorker(name, self._active_template_mgr, dpi_factor=dpi_factor, generation=generation)
        thread = QThread(self)
        worker.moveToThread(thread)
        worker.finished.connect(self._on_preview_finished)
        worker.finished.connect(thread.quit)
        thread.started.connect(worker.run)
        thread.finished.connect(thread.deleteLater)

        self._preview_worker = worker
        self._preview_thread = thread
        thread.start()

    def _on_preview_finished(self, name: str, png_bytes: bytes, dpi_factor: float, generation: int,
                              x_min: float, x_max: float, y_min: float, y_max: float):
        """Called on the main thread when a background render completes."""
        # Ignore stale results from cancelled renders
        if generation != self._preview_generation:
            return
        if self._tmpl_current_name == name:
            if png_bytes:
                pixmap = QPixmap()
                pixmap.loadFromData(png_bytes)
                if not pixmap.isNull():
                    self._tmpl_axis_bounds = (x_min, x_max, y_min, y_max)
                    if self._preview_fit_on_next:
                        self._tmpl_preview_lbl.set_pixmap(pixmap)
                    else:
                        self._tmpl_preview_lbl.update_pixmap_at_scale(pixmap, dpi_factor)
                    return
            if self._preview_fit_on_next:
                self._tmpl_preview_lbl.set_text(tr("msg_preview_unavailable"))

    def _on_preview_zoom_changed(self, zoom: float):
        """Re-render the current template at a DPI proportional to the zoom level."""
        if self._tmpl_current_name is None:
            return
        # Cap DPI factor at 4× (384 DPI) to keep memory reasonable
        dpi_factor = min(4.0, max(1.0, zoom))
        self._start_preview_render(self._tmpl_current_name, dpi_factor=dpi_factor, fit=False)

    def _render_template_preview(self, template_name: str) -> "QPixmap | None":
        """Render a DXF template to a QPixmap using the ezdxf drawing addon."""
        doc = self._template_mgr.load_template(template_name)
        if doc is None:
            print(f"[preview] load_template returned None for {template_name!r}")
            return None
        try:
            import io as _io
            from matplotlib.figure import Figure
            from matplotlib.backends.backend_agg import FigureCanvasAgg
            from ezdxf.addons.drawing import RenderContext, Frontend
            from ezdxf.addons.drawing.matplotlib import MatplotlibBackend

            fig = Figure(figsize=(5, 3.5), facecolor="white")
            FigureCanvasAgg(fig)
            ax = fig.add_axes([0, 0, 1, 1])
            ax.set_axis_off()
            ctx = RenderContext(doc)
            backend = MatplotlibBackend(ax)
            Frontend(ctx, backend).draw_layout(doc.modelspace(), finalize=True)
            buf = _io.BytesIO()
            fig.savefig(buf, format="png", dpi=96, bbox_inches="tight", facecolor="white")
            buf.seek(0)
            pixmap = QPixmap()
            pixmap.loadFromData(buf.read())
            return pixmap
        except Exception as exc:
            import traceback
            print(f"[preview] render failed for {template_name!r}: {exc}")
            traceback.print_exc()
            return None

    def _refresh_ctrl_template_list(self):
        self._ctrl_tmpl_list.clear()
        for name in self._ctrl_template_mgr.list_templates():
            self._ctrl_tmpl_list.addItem(name)

    def _import_ctrl_template(self):
        path, _ = QFileDialog.getOpenFileName(
            self, tr("msg_import_template_title"), "",
            tr("msg_import_filter"),
        )
        if not path:
            return
        name, ok = QInputDialog.getText(
            self, tr("msg_template_name_title"), tr("msg_template_name_prompt"),
            text=Path(path).stem,
        )
        if not ok or not name.strip():
            return
        success, msg = self._ctrl_template_mgr.save_template(path, name.strip())
        if success:
            QMessageBox.information(self, tr("msg_import_success_title"), msg)
            self._refresh_ctrl_template_list()
            items = self._ctrl_tmpl_list.findItems(name.strip(), Qt.MatchExactly)
            if items:
                self._ctrl_tmpl_list.setCurrentItem(items[0])
        else:
            QMessageBox.critical(self, tr("msg_import_error_title"), msg)

    def _delete_ctrl_template(self):
        sel = self._ctrl_tmpl_list.currentItem()
        if not sel:
            QMessageBox.warning(self, tr("msg_delete_template_title"), tr("msg_delete_template_none"))
            return
        name = sel.text()
        if QMessageBox.question(self, tr("msg_confirm_delete_title"), tr("msg_confirm_delete", name=name)) == QMessageBox.Yes:
            ok, msg = self._ctrl_template_mgr.delete_template(name)
            if ok:
                self._refresh_ctrl_template_list()
            else:
                QMessageBox.critical(self, tr("msg_error_title"), msg)

    def _on_ctrl_template_selected(self, current, previous):
        """Update the Template tab when a controller template is selected."""
        if current is None:
            return
        # Deselect the main template list without triggering its signal
        self._tmpl_list.blockSignals(True)
        self._tmpl_list.clearSelection()
        self._tmpl_list.setCurrentRow(-1)
        self._tmpl_list.blockSignals(False)
        # Deselect the IO template list without triggering its signal
        self._io_tmpl_list.blockSignals(True)
        self._io_tmpl_list.clearSelection()
        self._io_tmpl_list.setCurrentRow(-1)
        self._io_tmpl_list.blockSignals(False)

        self._tmpl_blocks = []
        self._tmpl_attr_values = {}
        self._tmpl_current_block = None
        self._tmpl_current_name = None
        self._tmpl_axis_bounds = None
        self._tmpl_block_list.clear()
        self._tmpl_attrib_table.blockSignals(True)
        self._tmpl_attrib_table.setRowCount(0)
        self._tmpl_attrib_table.blockSignals(False)
        self._tmpl_ios = []
        self._refresh_tmpl_io_table()

        name = current.text()
        self._tmpl_current_name = name
        self._active_template_mgr = self._ctrl_template_mgr
        self._active_tmpl_type = "controller"
        self._update_tmpl_io_ui()

        self._start_preview_render(name)

        self._tmpl_blocks = self._ctrl_template_mgr.get_template_blocks(name)
        if self._tmpl_blocks:
            for blk in self._tmpl_blocks:
                self._tmpl_block_list.addItem(blk["name"])
            self._tmpl_block_list.setCurrentRow(0)
        else:
            self._tmpl_attrib_status.setText(tr("msg_no_blocks"))

        self._tmpl_ios = self._ctrl_template_mgr.get_template_ios(name)
        self._refresh_tmpl_io_table()

    # ── IO template management ────────────────────────────────────────────────

    def _refresh_io_template_list(self):
        self._io_tmpl_list.clear()
        for name in self._io_template_mgr.list_templates():
            self._io_tmpl_list.addItem(name)

    def _import_io_template(self):
        path, _ = QFileDialog.getOpenFileName(
            self, tr("msg_import_template_title"), "",
            tr("msg_import_filter"),
        )
        if not path:
            return
        name, ok = QInputDialog.getText(
            self, tr("msg_template_name_title"), tr("msg_template_name_prompt"),
            text=Path(path).stem,
        )
        if not ok or not name.strip():
            return
        success, msg = self._io_template_mgr.save_template(path, name.strip())
        if success:
            QMessageBox.information(self, tr("msg_import_success_title"), msg)
            self._refresh_io_template_list()
            items = self._io_tmpl_list.findItems(name.strip(), Qt.MatchExactly)
            if items:
                self._io_tmpl_list.setCurrentItem(items[0])
        else:
            QMessageBox.critical(self, tr("msg_import_error_title"), msg)

    def _delete_io_template(self):
        sel = self._io_tmpl_list.currentItem()
        if not sel:
            QMessageBox.warning(self, tr("msg_delete_template_title"), tr("msg_delete_template_none"))
            return
        name = sel.text()
        if QMessageBox.question(self, tr("msg_confirm_delete_title"), tr("msg_confirm_delete", name=name)) == QMessageBox.Yes:
            ok, msg = self._io_template_mgr.delete_template(name)
            if ok:
                self._refresh_io_template_list()
            else:
                QMessageBox.critical(self, tr("msg_error_title"), msg)

    def _on_io_template_selected(self, current, previous):
        """Update the Template tab when an IO template is selected."""
        if current is None:
            self._io_tmpl_ins_x.blockSignals(True)
            self._io_tmpl_ins_y.blockSignals(True)
            self._io_tmpl_ins_x.setValue(0.0)
            self._io_tmpl_ins_y.setValue(0.0)
            self._io_tmpl_ins_x.blockSignals(False)
            self._io_tmpl_ins_y.blockSignals(False)
            return

        # Deselect main and controller template lists without triggering their signals
        self._tmpl_list.blockSignals(True)
        self._tmpl_list.clearSelection()
        self._tmpl_list.setCurrentRow(-1)
        self._tmpl_list.blockSignals(False)

        self._ctrl_tmpl_list.blockSignals(True)
        self._ctrl_tmpl_list.clearSelection()
        self._ctrl_tmpl_list.setCurrentRow(-1)
        self._ctrl_tmpl_list.blockSignals(False)

        self._tmpl_blocks = []
        self._tmpl_attr_values = {}
        self._tmpl_current_block = None
        self._tmpl_current_name = None
        self._tmpl_axis_bounds = None
        self._tmpl_block_list.clear()
        self._tmpl_attrib_table.blockSignals(True)
        self._tmpl_attrib_table.setRowCount(0)
        self._tmpl_attrib_table.blockSignals(False)
        self._tmpl_ios = []
        self._refresh_tmpl_io_table()

        name = current.text()
        self._tmpl_current_name = name
        self._active_template_mgr = self._io_template_mgr
        self._active_tmpl_type = "io"
        self._update_tmpl_io_ui()

        self._start_preview_render(name)

        self._tmpl_blocks = self._io_template_mgr.get_template_blocks(name)
        if self._tmpl_blocks:
            for blk in self._tmpl_blocks:
                self._tmpl_block_list.addItem(blk["name"])
            self._tmpl_block_list.setCurrentRow(0)
        else:
            self._tmpl_attrib_status.setText(tr("msg_no_blocks"))

        self._tmpl_ios = self._io_template_mgr.get_template_ios(name)
        self._refresh_tmpl_io_table()

        # Load insertion point
        x, y = self._io_template_mgr.get_insertion_point(name)
        self._io_tmpl_ins_x.blockSignals(True)
        self._io_tmpl_ins_y.blockSignals(True)
        self._io_tmpl_ins_x.setValue(x)
        self._io_tmpl_ins_y.setValue(y)
        self._io_tmpl_ins_x.blockSignals(False)
        self._io_tmpl_ins_y.blockSignals(False)

    def _update_tmpl_io_ui(self) -> None:
        """Show/hide Add button and update section title based on active template type."""
        is_io = self._active_tmpl_type == "io"
        self._btn_add_tmpl_io.setVisible(not is_io)
        if is_io:
            self._grp_tmpl_ios.setTitle(tr("grp_io_template_channels"))
        else:
            self._grp_tmpl_ios.setTitle(tr("grp_template_ios"))

    def _open_io_template_config(self, item) -> None:
        """Open the IO template config dialog on double-click."""
        name = item.text()
        ios = self._io_template_mgr.get_template_ios(name)
        dlg = IOTemplateConfigDialog(
            self,
            template_name=name,
            ios=ios,
            io_types=self._io_types,
        )
        if dlg.exec() == QDialog.Accepted and dlg.result_ios is not None:
            self._io_template_mgr.set_template_ios(name, dlg.result_ios)
            # Refresh the inline IO table if this template is currently shown
            if self._tmpl_current_name == name:
                self._tmpl_ios = dlg.result_ios
                self._refresh_tmpl_io_table()

    def _on_io_tmpl_ins_changed(self):
        """Save the insertion point for the currently selected IO template."""
        sel = self._io_tmpl_list.currentItem()
        if sel is None:
            return
        self._io_template_mgr.set_insertion_point(
            sel.text(),
            self._io_tmpl_ins_x.value(),
            self._io_tmpl_ins_y.value(),
        )

    def _refresh_template_list(self):
        self._tmpl_list.clear()
        for name in self._template_mgr.list_templates():
            self._tmpl_list.addItem(name)

    def _import_template(self):
        path, _ = QFileDialog.getOpenFileName(
            self, tr("msg_import_template_title"), "",
            tr("msg_import_filter"),
        )
        if not path:
            return
        name, ok = QInputDialog.getText(
            self, tr("msg_template_name_title"), tr("msg_template_name_prompt"),
            text=Path(path).stem,
        )
        if not ok or not name.strip():
            return
        success, msg = self._template_mgr.save_template(path, name.strip())
        if success:
            QMessageBox.information(self, tr("msg_import_success_title"), msg)
            self._refresh_template_list()
            # Select the newly imported template so the preview updates
            items = self._tmpl_list.findItems(name.strip(), Qt.MatchExactly)
            if items:
                self._tmpl_list.setCurrentItem(items[0])
        else:
            QMessageBox.critical(self, tr("msg_import_error_title"), msg)

    def _delete_template(self):
        sel = self._tmpl_list.currentItem()
        if not sel:
            QMessageBox.warning(self, tr("msg_delete_template_title"), tr("msg_delete_template_none"))
            return
        name = sel.text()
        if QMessageBox.question(self, tr("msg_confirm_delete_title"), tr("msg_confirm_delete", name=name)) == QMessageBox.Yes:
            ok, msg = self._template_mgr.delete_template(name)
            if ok:
                self._refresh_template_list()
            else:
                QMessageBox.critical(self, tr("msg_error_title"), msg)

    def _open_template_folder(self):
        import subprocess
        subprocess.Popen(["explorer", str(self._template_mgr.templates_dir)])

    def _open_ctrl_template_folder(self):
        import subprocess
        subprocess.Popen(["explorer", str(self._ctrl_template_mgr.templates_dir)])

    def _open_io_template_folder(self):
        import subprocess
        subprocess.Popen(["explorer", str(self._io_template_mgr.templates_dir)])

    def _on_tmpl_block_selected(self, row: int):
        """Populate the attribute table for the selected block."""
        # Save whatever is currently displayed before switching
        self._save_tmpl_attrib_values()

        self._tmpl_attrib_table.blockSignals(True)
        self._tmpl_attrib_table.setRowCount(0)

        if row < 0 or row >= len(self._tmpl_blocks):
            self._tmpl_attrib_status.setText(tr("msg_select_block"))
            self._tmpl_current_block = None
            self._tmpl_attrib_table.blockSignals(False)
            return

        blk = self._tmpl_blocks[row]
        self._tmpl_current_block = blk["handle"]
        attrs = blk["attributes"]
        saved = self._tmpl_attr_values.get(blk["handle"], {})

        if not attrs:
            self._tmpl_attrib_status.setText(tr("msg_no_attribs"))
            self._tmpl_attrib_table.blockSignals(False)
            return

        self._tmpl_attrib_status.setText("")
        _ro = Qt.ItemIsEnabled | Qt.ItemIsSelectable

        for attr in attrs:
            r = self._tmpl_attrib_table.rowCount()
            self._tmpl_attrib_table.insertRow(r)

            # Columns 0-Tag, 1-Prompt, 2-Default, 3-Value(editable), 4-Flags
            for col, key in ((0, "tag"), (1, "prompt"), (2, "default"), (4, "flags")):
                it = QTableWidgetItem(attr.get(key, ""))
                it.setFlags(_ro)
                self._tmpl_attrib_table.setItem(r, col, it)

            tag = attr.get("tag", "")
            val_item = QTableWidgetItem(saved.get(tag, ""))
            self._tmpl_attrib_table.setItem(r, 3, val_item)

        self._tmpl_attrib_table.blockSignals(False)
        self._zoom_to_block(blk)

    def _zoom_to_block(self, blk: dict):
        """Pan/zoom the preview to the INSERT position of *blk*."""
        if self._tmpl_axis_bounds is None:
            return
        if self._tmpl_preview_lbl._pixmap_item is None:
            return
        x_min, x_max, y_min, y_max = self._tmpl_axis_bounds
        dx = x_max - x_min
        dy = y_max - y_min
        if dx == 0 or dy == 0:
            return
        px_img = self._tmpl_preview_lbl._pixmap_item.pixmap().width()
        py_img = self._tmpl_preview_lbl._pixmap_item.pixmap().height()
        dxf_x, dxf_y = blk["insert_pt"]
        # Map DXF coords → pixmap pixel coords (y is flipped)
        px = (dxf_x - x_min) / dx * px_img
        py = (1.0 - (dxf_y - y_min) / dy) * py_img
        # Zoom window: 12 % of the smaller image dimension around the insert point
        margin = min(px_img, py_img) * 0.12
        rect = QRectF(px - margin, py - margin, margin * 2, margin * 2)
        self._tmpl_preview_lbl.zoom_to_rect(rect)

    def _save_tmpl_attrib_values(self):
        """Persist the current table's Value column into _tmpl_attr_values."""
        if self._tmpl_current_block is None:
            return
        values = {}
        for r in range(self._tmpl_attrib_table.rowCount()):
            tag_item = self._tmpl_attrib_table.item(r, 0)
            val_item = self._tmpl_attrib_table.item(r, 3)
            if tag_item and val_item:
                values[tag_item.text()] = val_item.text()
        self._tmpl_attr_values[self._tmpl_current_block] = values

    def _on_tmpl_attrib_changed(self, item: QTableWidgetItem):
        """Live-update _tmpl_attr_values when the user edits the Value column."""
        if item.column() != 3 or self._tmpl_current_block is None:
            return
        tag_item = self._tmpl_attrib_table.item(item.row(), 0)
        if tag_item:
            self._tmpl_attr_values.setdefault(
                self._tmpl_current_block, {}
            )[tag_item.text()] = item.text()

    # ── Generation ────────────────────────────────────────────────────────────

    def _new_drawing(self):
        if not self._confirm_discard():
            return
        self._clear_project()
        self._project_path = None
        self._dirty = False
        self._update_window_title()

    # ── Project persistence ───────────────────────────────────────────────────

    def _confirm_discard(self) -> bool:
        """Return True if it's safe to discard the current project."""
        if not self._dirty:
            return True
        reply = QMessageBox.question(
            self,
            tr("msg_unsaved_title"),
            tr("msg_unsaved_body"),
            QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel,
        )
        if reply == QMessageBox.Save:
            return self._save_project()
        return reply == QMessageBox.Discard

    def _clear_project(self):
        """Reset all in-memory project data and refresh every UI widget."""
        self._rungs.clear()
        self._io_items.clear()
        self._project_circuit_refs.clear()
        self._e_title.setText("ELECTRICAL DRAWING")
        self._e_project.setText("")
        self._e_dwgno.setText("001")
        self._e_rev.setText("A")
        self._e_drawnby.setText("")
        self._paper_cb.setCurrentText("A3 Landscape")
        self._refresh_io_table()
        self._refresh_project_circuits_table()

    def _update_window_title(self):
        name = Path(self._project_path).name if self._project_path else tr("msg_untitled")
        dirty = " \u25cf" if self._dirty else ""
        self.setWindowTitle(f"{tr('app_title')} \u2014 {name}{dirty}")

    def _mark_dirty(self):
        if not self._dirty:
            self._dirty = True
            self._update_window_title()

    def _collect_settings(self) -> dict:
        return {
            "title":          self._e_title.text().strip(),
            "project":        self._e_project.text().strip(),
            "drawing_number": self._e_dwgno.text().strip(),
            "revision":       self._e_rev.text().strip(),
            "drawn_by":       self._e_drawnby.text().strip(),
            "paper_size":     self._paper_cb.currentText(),
            "module":         self._module_cb.currentText(),
        }

    def _apply_settings(self, s: dict):
        self._e_title.setText(s.get("title", "ELECTRICAL DRAWING"))
        self._e_project.setText(s.get("project", ""))
        self._e_dwgno.setText(s.get("drawing_number", "001"))
        self._e_rev.setText(s.get("revision", "A"))
        self._e_drawnby.setText(s.get("drawn_by", ""))
        paper = s.get("paper_size", "A3 Landscape")
        if paper in _PAPER_SIZES:
            self._paper_cb.setCurrentText(paper)
        module = s.get("module", "")
        idx = self._module_cb.findText(module)
        self._module_cb.setCurrentIndex(idx if idx >= 0 else 0)

    def _open_project(self):
        if not self._confirm_discard():
            return
        path, _ = QFileDialog.getOpenFileName(
            self, tr("msg_open_project_title"), "",
            pm.FILE_FILTER,
        )
        if not path:
            return
        ok, msg, data = pm.load_project(path)
        if not ok:
            QMessageBox.critical(self, tr("msg_error_title"), msg)
            return
        self._clear_project()
        self._apply_settings(data.get("settings", {}))
        self._project_circuit_refs = list(data.get("project_circuits", []))
        for r in data.get("rungs", []):
            comps = [Component(**c) for c in r.pop("components", [])]
            self._rungs.append(Rung(components=comps, **r))
        self._refresh_io_table()
        self._refresh_project_circuits_table()
        self._project_path = path
        self._dirty = False
        self._update_window_title()

    def _save_project(self) -> bool:
        """Save to current path; prompt for path if none. Returns True on success."""
        if not self._project_path:
            return self._save_project_as()
        ok, msg = pm.save_project(
            self._project_path,
            self._collect_settings(),
            self._project_circuit_refs,
            self._io_items,
            self._rungs,
        )
        if ok:
            self._dirty = False
            self._update_window_title()
        else:
            QMessageBox.critical(self, tr("msg_error_title"), msg)
        return ok

    def _save_project_as(self) -> bool:
        path, _ = QFileDialog.getSaveFileName(
            self, tr("msg_save_project_title"), "",
            pm.FILE_FILTER,
        )
        if not path:
            return False
        if not path.endswith(pm.FILE_EXTENSION):
            path += pm.FILE_EXTENSION
        self._project_path = path
        return self._save_project()

    def _build_config(self) -> LadderConfig:
        pw, ph = _PAPER_SIZES.get(self._paper_cb.currentText(), (420, 297))
        return LadderConfig(
            title=self._e_title.text().strip() or "ELECTRICAL DRAWING",
            project=self._e_project.text().strip(),
            drawing_number=self._e_dwgno.text().strip() or "001",
            revision=self._e_rev.text().strip() or "A",
            drawn_by=self._e_drawnby.text().strip(),
            paper_width=pw,
            paper_height=ph,
        )

    # ── Generation value substitution ────────────────────────────────────────

    def _apply_generation_substitutions(
        self,
        rungs: list,
        io_items: list,
        config: "LadderConfig",
    ) -> tuple[list, list, "LadderConfig"]:
        """Apply all value substitutions required before generating the project.

        This is the central place to transform data before it reaches the
        drawing generator.  Each substitution block should be clearly
        commented so new rules can be added here over time.

        Parameters
        ----------
        rungs     : ladder rungs to be drawn
        io_items  : resolved IO items
        config    : drawing configuration

        Returns the (possibly modified) rungs, io_items, and config.
        """
        # ── Future substitutions go here ─────────────────────────────────────
        # Example structure:
        #   for rung in rungs:
        #       for component in rung.components:
        #           component.tag = component.tag.replace(...)


        #$, $+1
        return rungs, io_items, config

    def _enrich_io_item(
        self,
        io_item: "IOItem",
        ctrl_idx: int,
        slot_idx: int,
        io_type: str,
    ) -> "IOItem":
        """Return a copy of *io_item* with computed fields filled in.

        Called once per slot before the IO template is placed on the drawing.
        *io_item* is never modified; a new dataclass instance is returned.

        Args:
            io_item:   The original IO point.
            ctrl_idx:  1-based controller/module index (page number).
            slot_idx:  0-based slot position within the module.
            io_type:   ``"Input"`` or ``"Output"``.
        """
        import dataclasses as _dc
        copy = _dc.replace(io_item)

        # Build address like "II101" (Input, module 1, slot 01) or "OA201"
        type_prefix = io_type[0].upper()  # "I" or "O"
        sig_prefix = (io_item.signal_type[0].upper() if io_item.signal_type else "D")
        copy.address = f"{sig_prefix}{type_prefix}{ctrl_idx}{slot_idx + 1:02d}"
        return copy

    def _generate(self):
        if not self._project_circuit_refs:
            QMessageBox.warning(self, tr("msg_generate_title"), tr("msg_generate_no_circuits"))
            return

        # Ask user to pick a parent folder
        parent_dir = QFileDialog.getExistingDirectory(
            self, tr("msg_save_drawing_title"), ""
        )
        if not parent_dir:
            return

        # Create a project subfolder named after the project
        project_name = self._e_project.text().strip() or "output"
        safe_name = "".join(c if c.isalnum() or c in " _-" else "_" for c in project_name)
        output_dir = Path(parent_dir) / safe_name
        output_dir.mkdir(parents=True, exist_ok=True)

        config = self._build_config()
        rungs, io_items, config = self._apply_generation_substitutions(
            self._rungs, self._io_items, config
        )

        # Determine if DWG conversion is available
        oda = _find_oda_converter()
        use_dwg = oda is not None

        page = 1
        generated_dxf: list[Path] = []
        errors: list[str] = []

        for circuit_name in self._project_circuit_refs:
            circuit = self._lookup_circuit(circuit_name)
            if circuit is None:
                continue
            templates = circuit.templates if circuit.templates else []
            for tmpl_name in templates:
                page_str = f"E{page:03d}"
                dxf_path = output_dir / f"{page_str}.dxf"

                template_doc = self._template_mgr.load_template(tmpl_name) if tmpl_name else None

                page_config = dataclasses.replace(config, drawing_number=page_str)
                gen = DrawingGenerator(page_config)
                ok, msg = gen.generate(rungs, str(dxf_path), template_doc, io_items=io_items, controller_number=page)
                if ok:
                    generated_dxf.append(dxf_path)
                else:
                    errors.append(f"{page_str}: {msg}")
                page += 1

        # ── Controller pages ──────────────────────────────────────────────────
        # Calculate how many controller pages are needed based on the selected
        # module's IO capacity and the total IOs in the project.
        module_name = self._module_cb.currentText()
        module_def = next((m for m in self._modules if m.get("name") == module_name), None)
        if module_def and self._io_items:
            mod_inputs  = len(module_def.get("inputs", []))
            mod_outputs = len(module_def.get("outputs", []))
            total_inputs  = sum(1 for io in self._io_items if io.io_type == "Input")
            total_outputs = sum(1 for io in self._io_items if io.io_type == "Output")

            num_ctrl = 1  # at least one if a module is selected
            if mod_inputs > 0 and total_inputs > 0:
                num_ctrl = max(num_ctrl, math.ceil(total_inputs / mod_inputs))
            if mod_outputs > 0 and total_outputs > 0:
                num_ctrl = max(num_ctrl, math.ceil(total_outputs / mod_outputs))

            ctrl_tmpl_name = module_def.get("template", "")

            # Build a lookup: io_type_name → io type dict (from io_types_library)
            io_type_map = {t["name"]: t for t in self._io_types}

            # Split io_items by direction for paging
            input_ios  = [io for io in io_items if io.io_type == "Input"]
            output_ios = [io for io in io_items if io.io_type == "Output"]
            mod_input_slots  = module_def.get("inputs", [])
            mod_output_slots = module_def.get("outputs", [])

            for ctrl_idx in range(1, num_ctrl + 1):
                page_str = f"C{ctrl_idx:03d}"
                dxf_path = output_dir / f"{page_str}.dxf"
                # Reload a fresh copy of the templates for each page
                ctrl_tmpl_doc = (
                    self._ctrl_template_mgr.load_template(ctrl_tmpl_name)
                    if ctrl_tmpl_name else None
                )

                # Build per-slot IO template placements for this page
                io_template_placements: list = []

                # Inputs slice for this page
                start_in = (ctrl_idx - 1) * mod_inputs
                page_inputs = input_ios[start_in : start_in + mod_inputs]
                input_common_shared = module_def.get("input_common_shared", False)
                for slot_idx, io_item in enumerate(page_inputs):
                    io_type_def = io_type_map.get(io_item.io_type_name, {})
                    # Use shared_template for the second input in each pair (odd slot)
                    # when the module supports shared commons and the IO type is shared.
                    is_shared_slot = (
                        input_common_shared
                        and io_type_def.get("shared", False)
                        and slot_idx % 2 == 1
                    )
                    if is_shared_slot:
                        tmpl_name = io_type_def.get("shared_template", "") or io_type_def.get("io_template", "")
                    else:
                        tmpl_name = io_type_def.get("io_template", "")
                    if not tmpl_name or slot_idx >= len(mod_input_slots):
                        continue
                    tmpl_doc = self._io_template_mgr.load_template(tmpl_name)
                    if tmpl_doc is None:
                        continue
                    slot = mod_input_slots[slot_idx]
                    ip_x, ip_y = self._io_template_mgr.get_insertion_point(tmpl_name)
                    enriched = self._enrich_io_item(io_item, ctrl_idx, slot_idx, "Input")
                    io_template_placements.append(
                        (tmpl_doc, slot["x"] - ip_x, slot["y"] - ip_y, enriched)
                    )

                # Outputs slice for this page
                start_out = (ctrl_idx - 1) * mod_outputs
                page_outputs = output_ios[start_out : start_out + mod_outputs]
                for slot_idx, io_item in enumerate(page_outputs):
                    io_type_def = io_type_map.get(io_item.io_type_name, {})
                    tmpl_name = io_type_def.get("io_template", "")
                    if not tmpl_name or slot_idx >= len(mod_output_slots):
                        continue
                    tmpl_doc = self._io_template_mgr.load_template(tmpl_name)
                    if tmpl_doc is None:
                        continue
                    slot = mod_output_slots[slot_idx]
                    ip_x, ip_y = self._io_template_mgr.get_insertion_point(tmpl_name)
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
                    generated_dxf.append(dxf_path)
                else:
                    errors.append(f"{page_str}: {msg}")

        # Convert DXF → DWG if ODA converter is available
        if use_dwg and generated_dxf:
            converted, total_dxf, conv_error = convert_folder_dxf_to_dwg(str(output_dir))
            if conv_error:
                errors.append(f"DWG conversion: {conv_error}")
            if converted > 0:
                total = converted
                ext = "DWG"
            else:
                # Conversion failed entirely – keep DXF
                total = len(generated_dxf)
                ext = "DXF"
        else:
            total = len(generated_dxf)
            ext = "DXF"

        summary = f"{total} {ext} file(s) saved to:\n{output_dir}"
        if errors:
            summary += "\n\nErrors:\n" + "\n".join(errors)
            QMessageBox.warning(self, tr("msg_generate_title"), summary)
        else:
            QMessageBox.information(self, tr("msg_success_title"), summary)

        # Open the output folder in the file explorer
        try:
            os.startfile(str(output_dir))
        except AttributeError:
            import subprocess
            subprocess.Popen(["xdg-open", str(output_dir)])

    # ── Retranslation & language ──────────────────────────────────────────────

    def _retranslate_ui(self) -> None:
        self._update_window_title()
        # Menus
        self._menu_file.setTitle(tr("menu_file"))
        self._act_new.setText(tr("menu_new_drawing"))
        self._act_open_project.setText(tr("menu_open_project"))
        self._act_save_project.setText(tr("menu_save_project"))
        self._act_save_project_as.setText(tr("menu_save_project_as"))
        self._act_exit.setText(tr("menu_exit"))
        self._menu_templates.setTitle(tr("menu_templates"))
        self._act_import_tmpl.setText(tr("menu_import_template"))
        self._act_del_tmpl.setText(tr("menu_delete_template"))
        self._menu_lang.setTitle(tr("menu_language"))
        self._menu_help.setTitle(tr("menu_help"))
        self._act_about.setText(tr("menu_about"))
        # Left panel
        self._grp_settings.setTitle(tr("grp_settings"))
        self._lbl_title_w.setText(tr("lbl_title"))
        self._lbl_project_w.setText(tr("lbl_project"))
        self._lbl_drawing_no_w.setText(tr("lbl_drawing_no"))
        self._lbl_revision_w.setText(tr("lbl_revision"))
        self._lbl_drawn_by_w.setText(tr("lbl_drawn_by"))
        self._lbl_paper_size_w.setText(tr("lbl_paper_size"))
        self._lbl_module_w.setText(tr("lbl_module"))
        self._tmpl_type_tabs.setTabText(0, tr("grp_templates"))
        self._tmpl_type_tabs.setTabText(1, tr("grp_ctrl_templates"))
        self._tmpl_type_tabs.setTabText(2, tr("grp_io_templates"))
        self._btn_import_tmpl.setText(tr("btn_import"))
        self._btn_delete_tmpl.setText(tr("btn_delete"))
        self._btn_open_tmpl_folder.setText(tr("btn_open_folder"))
        self._btn_import_ctrl_tmpl.setText(tr("btn_import"))
        self._btn_delete_ctrl_tmpl.setText(tr("btn_delete"))
        self._btn_open_ctrl_tmpl_folder.setText(tr("btn_open_folder"))
        self._btn_import_io_tmpl.setText(tr("btn_import"))
        self._btn_delete_io_tmpl.setText(tr("btn_delete"))
        self._btn_open_io_tmpl_folder.setText(tr("btn_open_folder"))
        self._lbl_io_tmpl_ins_x.setText(tr("lbl_io_tmpl_ins_x"))
        self._lbl_io_tmpl_ins_y.setText(tr("lbl_io_tmpl_ins_y"))
        self._btn_generate.setText(tr("btn_generate"))
        # Tabs
        self._tabs.setTabText(0, tr("tab_io"))
        self._tabs.setTabText(1, tr("tab_template"))
        self._tabs.setTabText(2, tr("tab_circuits"))
        self._tabs.setTabText(3, tr("tab_rules"))
        self._tabs.setTabText(4, tr("tab_modules"))
        self._tabs.setTabText(5, tr("tab_valves"))
        self._tabs.setTabText(6, tr("tab_io_types"))
        # IO Types tab
        self._lbl_io_types_hdr.setText(tr("lbl_io_types_hdr"))
        self._btn_add_io_type.setText(tr("btn_add_io_type"))
        self._btn_edit_io_type.setText(tr("btn_edit_io_type"))
        self._btn_remove_io_type.setText(tr("btn_remove"))
        self._io_types_table.setHorizontalHeaderLabels([
            tr("col_io_type_name"), tr("col_description"),
            tr("col_signal_category"), tr("col_io_direction"), tr("col_io_template"),
            tr("col_io_type_shared"), tr("col_io_type_shared_template"),
        ])
        # Circuits tab
        _circuit_cols = [
            tr("col_rung_num"),
            tr("col_circuit_name"),
            tr("col_circuit_number"),
            tr("col_description"),
            tr("col_circuit_templates"),
        ]
        self._lbl_library_hdr.setText(tr("lbl_library_hdr"))
        self._btn_add_lib_circuit.setText(tr("btn_add_circuit"))
        self._btn_edit_lib_circuit.setText(tr("btn_edit_circuit"))
        self._btn_remove_lib_circuit.setText(tr("btn_remove_lib_circuit"))
        self._library_circuit_table.setHorizontalHeaderLabels(_circuit_cols)
        self._lbl_project_circuits_hdr.setText(tr("lbl_project_circuits_hdr"))
        self._btn_add_to_project.setText(tr("btn_add_to_project"))
        self._btn_remove_project_circuit.setText(tr("btn_remove"))
        self._btn_project_circuit_up.setText(tr("btn_move_up"))
        self._btn_project_circuit_down.setText(tr("btn_move_down"))
        self._project_circuit_table.setHorizontalHeaderLabels(_circuit_cols)
        # Template tab
        self._grp_tmpl_preview.setTitle(tr("grp_template_preview"))
        if self._tmpl_preview_lbl._pixmap_item is None:
            self._tmpl_preview_lbl.set_text(tr("msg_preview_none"))
        self._grp_tmpl_blocks.setTitle(tr("grp_blocks_list"))
        self._grp_tmpl_attribs.setTitle(tr("grp_block_attribs"))
        self._tmpl_attrib_table.setHorizontalHeaderLabels([
            tr("col_attrib_tag"), tr("col_attrib_prompt"),
            tr("col_attrib_default"), tr("col_attrib_value"), tr("col_attrib_flags"),
        ])
        # Template I/O list
        self._update_tmpl_io_ui()
        self._btn_add_tmpl_io.setText(tr("btn_add_template_io"))
        self._btn_edit_tmpl_io.setText(tr("btn_edit_template_io"))
        self._btn_remove_tmpl_io.setText(tr("btn_remove"))
        self._tmpl_io_table.setHorizontalHeaderLabels([
            tr("col_io_name"), tr("col_description"), tr("col_signal_type"),
            tr("col_io_direction"), tr("col_io_type"),
        ])
        # I/O tab
        self._lbl_io_hdr.setText(tr("lbl_io_header"))
        self._btn_refresh_io.setText(tr("btn_refresh_io"))
        self._io_table.setHorizontalHeaderLabels([
            tr("col_circuit"), tr("col_circuit_number"), tr("col_template"),
            tr("col_io_name"), tr("col_description"),
            tr("col_signal_type"), tr("col_io_direction"), tr("col_io_type"),
        ])
        # Rules tab
        self._lbl_rules_hdr.setText(tr("lbl_rules_hdr"))
        self._btn_add_rule.setText(tr("btn_add_rule"))
        self._btn_edit_rule.setText(tr("btn_edit_rule"))
        self._btn_remove_rule.setText(tr("btn_remove"))
        self._btn_rule_up.setText(tr("btn_move_up"))
        self._btn_rule_down.setText(tr("btn_move_down"))
        self._rules_table.setHorizontalHeaderLabels([
            tr("col_rule_name"), tr("col_rule_description"),
        ])
        # Modules tab
        self._lbl_modules_hdr.setText(tr("lbl_modules_hdr"))
        self._btn_add_module.setText(tr("btn_add_module"))
        self._btn_edit_module.setText(tr("btn_edit_module"))
        self._btn_remove_module.setText(tr("btn_remove"))
        self._btn_module_up.setText(tr("btn_move_up"))
        self._btn_module_down.setText(tr("btn_move_down"))
        self._btn_manage_io_values.setText(tr("btn_manage_io_values"))
        self._modules_table.setHorizontalHeaderLabels([
            tr("col_rung_num"), tr("col_module_name"), tr("col_module_company"),
            tr("col_description"), tr("col_module_other_ios"),
        ])
        # Valves tab
        self._lbl_valve_type_hdr.setText(tr("lbl_valve_type_hdr"))
        self._lbl_valve_ios_hdr.setText(tr("lbl_valve_ios_hdr"))
        self._lbl_project_valves_hdr.setText(tr("lbl_circuit_valves_hdr"))
        self._lbl_select_circuit.setText(tr("lbl_filter_circuit"))
        self._btn_add_valve_type.setText(tr("btn_add_valve_type"))
        self._btn_rename_valve_type.setText(tr("btn_rename_valve_type"))
        self._btn_remove_valve_type.setText(tr("btn_remove_valve_type"))
        self._btn_add_valve_io.setText(tr("btn_add_valve_io"))
        self._btn_edit_valve_io.setText(tr("btn_edit_valve_io"))
        self._btn_remove_valve_io.setText(tr("btn_remove"))
        self._valve_io_table.setHorizontalHeaderLabels([
            tr("col_io_name"), tr("col_description"), tr("col_signal_type"),
            tr("col_io_direction"), tr("col_io_type"),
        ])
        self._btn_add_valve.setText(tr("btn_add_valve"))
        self._btn_edit_valve.setText(tr("btn_edit_valve"))
        self._btn_remove_valve.setText(tr("btn_remove"))
        self._valve_table.setHorizontalHeaderLabels([
            tr("col_valve_tag"), tr("col_valve_type"), tr("col_description"),
            tr("col_valve_circuit"),
        ])
        self._lbl_valve_template.setText(tr("lbl_valve_template"))
        self._lbl_valve_qty.setText(tr("lbl_valve_qty"))
        # refresh the All option text in case language changed
        if self._valve_circuit_cb.count() > 0:
            self._valve_circuit_cb.setItemText(0, tr("opt_all_circuits"))

    def _change_language(self, lang: str) -> None:
        set_language(lang)
        self._retranslate_ui()

    def closeEvent(self, event):
        if self._confirm_discard():
            event.accept()
        else:
            event.ignore()

    def _about(self):
        QMessageBox.information(self, tr("msg_about_title"), tr("msg_about"))


