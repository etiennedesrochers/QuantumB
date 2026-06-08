"""
AutoCAD Electrical Drawing Generator
Main application entry point (PySide6 UI)
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

# PySide6 is installed at C:\pyside6 to work around Windows MAX_PATH limit
_PYSIDE6_PATH = Path(r"C:\pyside6")
if _PYSIDE6_PATH.exists() and str(_PYSIDE6_PATH) not in sys.path:
    sys.path.insert(0, str(_PYSIDE6_PATH))

# Ensure Qt can locate its platform plugins (fixes "windows" plugin not found on Windows)
import PySide6
os.environ.setdefault(
    "QT_QPA_PLATFORM_PLUGIN_PATH",
    str(Path(PySide6.__file__).parent / "plugins" / "platforms"),
)

from PySide6.QtWidgets import QApplication

from main_window import MainWindow


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
