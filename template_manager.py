"""
Template manager: import .dxf or .dwg files as base templates.
.dwg files require the ODA File Converter (free, optional) to be converted first.
"""
import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

import ezdxf
import ezdxf.recover
from ezdxf.document import Drawing

TEMPLATES_DIR = Path(__file__).parent / "templates"
TEMPLATES_DIR.mkdir(exist_ok=True)

CTRL_TEMPLATES_DIR = Path(__file__).parent / "templates" / "controller"
CTRL_TEMPLATES_DIR.mkdir(exist_ok=True)

IO_TEMPLATES_DIR = Path(__file__).parent / "templates" / "io"
IO_TEMPLATES_DIR.mkdir(exist_ok=True)


# ─────────────────────────────────────────────────────────────────────────────
# DWG → DXF conversion (optional, requires ODA File Converter)
# ─────────────────────────────────────────────────────────────────────────────

ODA_CONVERTER_PATHS = [
    r"C:\Program Files\ODA\ODAFileConverter\ODAFileConverter.exe",
    r"C:\Program Files (x86)\ODA\ODAFileConverter\ODAFileConverter.exe",
]

_ODA_SEARCH_ROOTS = [
    r"C:\Program Files\ODA",
    r"C:\Program Files (x86)\ODA",
]


def _find_oda_converter() -> str | None:
    # Check exact known paths first
    for p in ODA_CONVERTER_PATHS:
        if os.path.isfile(p):
            return p
    # Search for versioned subdirectories (e.g. "ODAFileConverter 27.1.0")
    for root in _ODA_SEARCH_ROOTS:
        root_path = Path(root)
        if root_path.is_dir():
            for candidate in sorted(root_path.glob("ODAFileConverter*"), reverse=True):
                exe = candidate / "ODAFileConverter.exe"
                if exe.is_file():
                    return str(exe)
    return None


def convert_dwg_to_dxf(dwg_path: str) -> str | None:
    """
    Attempt to convert a .dwg file to .dxf using the ODA File Converter.
    Returns the path to the converted .dxf or None on failure.
    """
    oda = _find_oda_converter()
    if oda is None:
        return None

    src = Path(dwg_path)
    out_dir = Path(tempfile.mkdtemp())

    try:
        subprocess.run(
            [
                oda,
                str(src.parent),  # input folder
                str(out_dir),     # output folder
                "ACAD2018",       # output version
                "DXF",            # output type
                "0",              # recurse subfolders
                "1",              # audit
                src.name,         # input file filter
            ],
            check=True,
            timeout=60,
        )
        candidates = list(out_dir.glob("*.dxf"))
        if candidates:
            return str(candidates[0])
    except Exception:
        pass
    return None


def convert_dxf_to_dwg(dxf_path: str) -> str | None:
    """
    Attempt to convert a single .dxf file to .dwg using the ODA File Converter.
    Returns the path to the converted .dwg or None on failure.
    """
    oda = _find_oda_converter()
    if oda is None:
        return None

    src = Path(dxf_path)
    # Copy the single file to a fresh temp input dir so ODA only sees one file
    in_dir = Path(tempfile.mkdtemp())
    out_dir = Path(tempfile.mkdtemp())
    tmp_src = in_dir / src.name
    shutil.copy2(src, tmp_src)

    try:
        subprocess.run(
            [
                oda,
                str(in_dir),   # input folder  (only our file)
                str(out_dir),  # output folder
                "ACAD2018",    # output version
                "DWG",         # output type
                "0",           # recurse subfolders
                "1",           # audit
            ],
            check=True,
            timeout=60,
        )
        candidates = list(out_dir.glob("*.dwg"))
        if candidates:
            dest = src.with_suffix(".dwg")
            shutil.move(str(candidates[0]), str(dest))
            return str(dest)
    except Exception:
        pass
    return None


def convert_folder_dxf_to_dwg(folder: str) -> tuple[int, int, str]:
    """
    Convert all .dxf files in *folder* to .dwg using the ODA File Converter
    in a single batch call.  The original .dxf files are deleted on success.

    Returns (converted_count, total_dxf_count, error_message).
    error_message is "" on full success.
    """
    oda = _find_oda_converter()
    if oda is None:
        return 0, 0, "ODA File Converter not found."

    folder_path = Path(folder)
    dxf_files = list(folder_path.glob("*.dxf"))
    if not dxf_files:
        return 0, 0, "No DXF files to convert."

    out_dir = Path(tempfile.mkdtemp())
    log_file = out_dir / "_oda_log.txt"

    try:
        # ODA File Converter is itself a Qt GUI app. Capturing stdout/stderr or
        # using CREATE_NO_WINDOW breaks its Qt platform initialisation when it is
        # launched from inside another Qt process.  Instead we redirect its output
        # to a log file so the pipes never block and it can start normally.
        with open(log_file, "w") as lf:
            proc = subprocess.run(
                [
                    oda,
                    str(folder_path),  # input folder
                    str(out_dir),      # output folder
                    "ACAD2018",        # output version
                    "DWG",             # output type
                    "0",               # recurse subfolders
                    "1",               # audit
                ],
                stdout=lf,
                stderr=lf,
                timeout=120,
            )
    except subprocess.TimeoutExpired:
        return 0, len(dxf_files), "ODA converter timed out."
    except Exception as exc:
        return 0, len(dxf_files), f"ODA subprocess error: {exc}"

    converted = 0
    for dwg in out_dir.glob("*.dwg"):
        dest = folder_path / dwg.name
        shutil.move(str(dwg), str(dest))
        dxf_counterpart = folder_path / dwg.with_suffix(".dxf").name
        if dxf_counterpart.exists():
            dxf_counterpart.unlink()
        converted += 1

    if converted == 0:
        log_text = ""
        try:
            log_text = log_file.read_text(errors="replace").strip()
        except Exception:
            pass
        return 0, len(dxf_files), (
            f"ODA ran (exit {proc.returncode}) but produced no DWG files.\n{log_text}"
        )

    return converted, len(dxf_files), ""


# ─────────────────────────────────────────────────────────────────────────────
# Template store
# ─────────────────────────────────────────────────────────────────────────────

class TemplateManager:
    """Manages saved template DXF files in the ./templates directory."""

    def __init__(self, templates_dir: Path | None = None):
        self.templates_dir = templates_dir if templates_dir is not None else TEMPLATES_DIR
        self.templates_dir.mkdir(exist_ok=True)
        self._ios_file = self.templates_dir / ".template_ios.json"
        # {template_name: (Drawing, mtime_float)}
        self._doc_cache: dict[str, tuple] = {}
        # {(template_name, dpi_int): (png_bytes, x_min, x_max, y_min, y_max)}
        self._png_cache: dict[tuple, tuple] = {}

    def _load_ios_store(self) -> dict:
        """Load the template IOs metadata file. Returns {} on any error."""
        if self._ios_file.exists():
            try:
                return json.loads(self._ios_file.read_text(encoding="utf-8"))
            except Exception:
                pass
        return {}

    def _save_ios_store(self, store: dict) -> None:
        self._ios_file.write_text(
            json.dumps(store, indent=2, ensure_ascii=False), encoding="utf-8"
        )

    # ── saving ──────────────────────────────────────────────────────────────

    def save_template(self, source_path: str, template_name: str) -> tuple[bool, str]:
        """
        Copy/convert *source_path* (.dxf or .dwg) into the templates folder
        under *template_name*.dxf.
        Returns (success, message).
        """
        src = Path(source_path)
        if not src.exists():
            return False, f"File not found: {source_path}"

        ext = src.suffix.lower()

        if ext == ".dwg":
            dxf_path = convert_dwg_to_dxf(source_path)
            if dxf_path is None:
                return (
                    False,
                    "DWG conversion failed. Install ODA File Converter or supply a .dxf file.",
                )
            src = Path(dxf_path)

        elif ext != ".dxf":
            return False, f"Unsupported file type: {ext}"

        dest = self.templates_dir / f"{template_name}.dxf"
        shutil.copy2(src, dest)
        # Invalidate caches so the next preview re-loads from the new file.
        self._doc_cache.pop(template_name, None)
        stale = [k for k in self._png_cache if k[0] == template_name]
        for k in stale:
            del self._png_cache[k]
        return True, f"Template '{template_name}' saved."

    # ── listing ─────────────────────────────────────────────────────────────

    def list_templates(self) -> list[str]:
        return [p.stem for p in sorted(self.templates_dir.glob("*.dxf"))]

    # ── loading ─────────────────────────────────────────────────────────────

    def load_template(self, template_name: str) -> Drawing | None:
        """Return an ezdxf Drawing object for *template_name*, or None.

        The result is cached in memory keyed by (name, mtime) so repeated
        calls for the same unchanged file skip the disk read entirely.
        """
        path = self.templates_dir / f"{template_name}.dxf"
        if not path.exists():
            return None
        try:
            mtime = path.stat().st_mtime
        except OSError:
            return None

        cached = self._doc_cache.get(template_name)
        if cached is not None and cached[1] == mtime:
            return cached[0]

        # Try the fast reader first; fall back to the recovery reader for
        # non-standard or DWG-converted files that may have structural quirks.
        doc = None
        try:
            doc = ezdxf.readfile(str(path))
        except Exception:
            try:
                doc, _ = ezdxf.recover.readfile(str(path))
            except Exception:
                return None

        self._doc_cache[template_name] = (doc, mtime)
        # Invalidate any PNG renders that were derived from the old version.
        stale = [k for k in self._png_cache if k[0] == template_name]
        for k in stale:
            del self._png_cache[k]
        return doc

    def get_png_cache(self, template_name: str, dpi: int) -> tuple | None:
        """Return cached (png_bytes, x_min, x_max, y_min, y_max) or None."""
        return self._png_cache.get((template_name, dpi))

    def set_png_cache(self, template_name: str, dpi: int,
                      png_bytes: bytes, x_min: float, x_max: float,
                      y_min: float, y_max: float) -> None:
        """Store a rendered PNG and its axis bounds in the cache.

        The cache is capped at 30 entries (templates × DPI levels) to avoid
        unbounded memory growth.
        """
        if len(self._png_cache) >= 30:
            self._png_cache.pop(next(iter(self._png_cache)))
        self._png_cache[(template_name, dpi)] = (png_bytes, x_min, x_max, y_min, y_max)

    def delete_template(self, template_name: str) -> tuple[bool, str]:
        path = self.templates_dir / f"{template_name}.dxf"
        if path.exists():
            path.unlink()
            # Remove associated IOs
            store = self._load_ios_store()
            if template_name in store:
                del store[template_name]
                self._save_ios_store(store)
            # Remove associated insertion point
            pts = self._load_insertion_points()
            if template_name in pts:
                del pts[template_name]
                self._save_insertion_points(pts)
            # Clear caches
            self._doc_cache.pop(template_name, None)
            stale = [k for k in self._png_cache if k[0] == template_name]
            for k in stale:
                del self._png_cache[k]
            return True, f"Template '{template_name}' deleted."
        return False, "Template not found."

    # ── insertion point ─────────────────────────────────────────────────────

    def get_insertion_point(self, template_name: str) -> tuple[float, float]:
        """Return the (x, y) insertion point saved for *template_name* (default 0, 0)."""
        pt = self._load_insertion_points().get(template_name, [0.0, 0.0])
        return (float(pt[0]), float(pt[1]))

    def set_insertion_point(self, template_name: str, x: float, y: float) -> None:
        """Persist the (x, y) insertion point for *template_name*."""
        pts = self._load_insertion_points()
        pts[template_name] = [x, y]
        self._save_insertion_points(pts)

    def _load_insertion_points(self) -> dict:
        f = self.templates_dir / ".insertion_points.json"
        if f.exists():
            try:
                return json.loads(f.read_text(encoding="utf-8"))
            except Exception:
                pass
        return {}

    def _save_insertion_points(self, store: dict) -> None:
        f = self.templates_dir / ".insertion_points.json"
        f.write_text(json.dumps(store, indent=2, ensure_ascii=False), encoding="utf-8")

    # ── template I/O list ───────────────────────────────────────────────────

    def get_template_ios(self, template_name: str) -> list[dict]:
        """Return the I/O list for *template_name* (list of dicts)."""
        return self._load_ios_store().get(template_name, [])

    def set_template_ios(self, template_name: str, ios: list[dict]) -> None:
        """Persist the I/O list for *template_name*."""
        store = self._load_ios_store()
        store[template_name] = ios
        self._save_ios_store(store)

    # ── block inspection ────────────────────────────────────────────────────

    def get_template_blocks(self, template_name: str) -> list[dict]:
        """Return info about every INSERT instance in the template.

        One entry is produced per INSERT entity found across all layouts, so
        blocks that appear multiple times in the drawing show up multiple times
        in the list.  Each entry is a dict::

            {
                "name":   str,   # block name
                "handle": str,   # DXF handle of the INSERT (unique per instance)
                "attributes": [
                    {"tag": str, "prompt": str, "default": str, "flags": str}
                ]
            }

        ``"default"`` holds the actual text value stored on the ATTRIB entity
        (i.e. the value already written into the drawing), not just the
        block-definition default.
        """
        _FLAG_LABELS = {1: "invisible", 2: "constant", 4: "verify", 8: "preset"}

        doc = self.load_template(template_name)
        if doc is None:
            return []

        result: list[dict] = []

        for layout in doc.layouts:
            for entity in layout:
                if entity.dxftype() != "INSERT":
                    continue
                block_name = entity.dxf.get("name", "")
                handle = entity.dxf.get("handle", "")

                # Build a prompt lookup from the block definition (ATTDEF has prompt; ATTRIB does not)
                prompt_map: dict[str, str] = {}
                if block_name in doc.blocks:
                    for attdef in doc.blocks[block_name]:
                        if attdef.dxftype() == "ATTDEF":
                            prompt_map[attdef.dxf.get("tag", "")] = attdef.dxf.get("prompt", "")

                attrs = []
                for attrib in entity.attribs:
                    tag = attrib.dxf.get("tag", "")
                    flags_val = attrib.dxf.get("flags", 0)
                    flag_parts = [
                        label for bit, label in _FLAG_LABELS.items() if flags_val & bit
                    ]
                    attrs.append({
                        "tag":     tag,
                        "prompt":  prompt_map.get(tag, ""),
                        "default": attrib.dxf.get("text", ""),
                        "flags":   ", ".join(flag_parts) if flag_parts else "—",
                    })

                # INSERT position in DXF model-space coordinates
                pt = entity.dxf.get("insert", None)
                insert_pt = (float(pt.x), float(pt.y)) if pt is not None else (0.0, 0.0)

                result.append({"name": block_name, "handle": handle, "insert_pt": insert_pt, "attributes": attrs})

        return result
