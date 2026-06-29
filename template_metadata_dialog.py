"""
Dialog for editing template metadata (ladder_type, part_of_ladder).
"""
from __future__ import annotations

from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QFormLayout,
    QLineEdit,
    QDialogButtonBox,
    QMessageBox,
)

from models import Template
from i18n import tr


class TemplateMetadataDialog(QDialog):
    """Add or edit template metadata (ladder_type and part_of_ladder)."""

    def __init__(self, parent=None, template_name: str = "", data: Template | None = None):
        super().__init__(parent)
        self.setWindowTitle("Template Metadata")
        self.setMinimumWidth(400)
        self.result_template: Template | None = None
        self._template_name = template_name
        self._build(data)

    def _build(self, data: Template | None):
        layout = QVBoxLayout(self)

        form = QFormLayout()

        # Template name (read-only or informational)
        self._name_lbl = QLineEdit(self._template_name)
        self._name_lbl.setReadOnly(True)
        form.addRow("Template Name:", self._name_lbl)

        # Ladder type
        self._ladder_type_edit = QLineEdit(data.ladder_type if data else "")
        self._ladder_type_edit.setPlaceholderText("e.g., 'io', 'controller', 'ladder'")
        form.addRow("Ladder Type:", self._ladder_type_edit)

        # Part of ladder
        self._part_of_ladder_edit = QLineEdit(str(data.part_of_ladder) if data else "")
        self._part_of_ladder_edit.setPlaceholderText("e.g., '1', '2', 'main', etc.")
        form.addRow("Part of Ladder:", self._part_of_ladder_edit)

        layout.addLayout(form)

        # Buttons
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self._ok)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _ok(self):
        ladder_type = self._ladder_type_edit.text().strip()
        part_of_ladder = self._part_of_ladder_edit.text().strip()

        # Create the Template object
        self.result_template = Template(
            name=self._template_name,
            ladder_type=ladder_type,
            part_of_ladder=part_of_ladder,
        )
        self.accept()
