"""Makes the frozen legacy engine (`legacy_code_interface/src/...`) importable.

The legacy code imports itself as `src.core.*`, so its own root must be on
`sys.path`. Nothing here modifies legacy files.
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
LEGACY_ROOT = REPO_ROOT / "legacy_code_interface"

CONFIG_DIR = LEGACY_ROOT / "config"
TEMPLATES_DIR = LEGACY_ROOT / "templates"
DATA_EXCEL_DIR = LEGACY_ROOT / "data_excel"
PROJECTS_DIR = LEGACY_ROOT / "projects"
PROJECTS_DIR.mkdir(exist_ok=True)


def ensure_legacy_importable() -> Path:
    """Put the legacy root on `sys.path` (idempotent) and return it."""
    path = str(LEGACY_ROOT)
    if path not in sys.path:
        sys.path.insert(0, path)
    return LEGACY_ROOT
