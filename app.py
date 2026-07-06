"""
AutoCAD Electrical Drawing Generator
Main application entry point - supports both GUI (PySide6) and CLI modes

GUI Mode (default):
    python app.py

CLI Mode (non-interactive):
    python app.py --project <file> --output <dir> [--format {dxf|dwg|both}]
"""
from __future__ import annotations

import os
import sys
import argparse
from pathlib import Path

# PySide6 is installed at C:\pyside6 to work around Windows MAX_PATH limit
_PYSIDE6_PATH = Path(r"C:\pyside6")
if _PYSIDE6_PATH.exists() and str(_PYSIDE6_PATH) not in sys.path:
    sys.path.insert(0, str(_PYSIDE6_PATH))


def _has_cli_args() -> bool:
    """Check if CLI arguments are present."""
    cli_indicators = {"--project", "--output", "--format", "--help", "-h"}
    return any(arg in sys.argv for arg in cli_indicators)


def _run_cli():
    """Run in CLI mode."""
    from cli import main as cli_main
    return cli_main()


def _run_gui():
    """Run in GUI mode."""
    # Ensure Qt can locate its platform plugins (fixes "windows" plugin not found on Windows)
    import PySide6
    os.environ.setdefault(
        "QT_QPA_PLATFORM_PLUGIN_PATH",
        str(Path(PySide6.__file__).parent / "plugins" / "platforms"),
    )

    from PySide6.QtWidgets import QApplication
    from main_window import MainWindow

    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    if _has_cli_args():
        # CLI mode
        exit_code = _run_cli()
        sys.exit(exit_code)
    else:
        # GUI mode
        _run_gui()
