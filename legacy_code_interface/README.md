
# QuantumB — AutoCAD Electrical Drawing Generator

QuantumB generates AutoCAD electrical ladder-diagram drawings (DXF/DWG) from
project data: circuits, I/O lists, valves, controller modules, and reusable
DXF templates. It ships as a desktop GUI, a scriptable CLI, and a web
interface, all built on the same core generation engine.

## Features

- **Project-based drawing generation** — define circuits, I/O items, rungs,
  valves, and controller modules in a `.aepj` project file and generate
  fully laid-out DXF (and optionally DWG) pages.
- **Template system** — import `.dxf`/`.dwg` files as reusable templates for
  controllers, I/O blocks, ladder base pages, ladder components, and valves.
- **Desktop GUI** (PySide6) — interactive project editor with live preview,
  template management, and Excel import/export of templates and I/O.
- **CLI mode** — non-interactive generation for automation/CI, from either a
  `.aepj` project file or an XNNOV Selection Tool JSON payload.
- **Web interface** (Flask) — browser-based circuit/compressor configurator
  that posts selections straight to the generator and returns a ZIP of the
  generated drawings.
- **DWG conversion** — optional conversion via the free ODA File Converter
  when generating `.dwg` output.

## Project layout

```
app.py                  # Entry point — dispatches to GUI or CLI mode
src/
  core/                  # Business logic: models, circuit/module/template/
                          # valve/rules managers, drawing generator, project
                          # manager, selection adapter, app config
  gui/                    # PySide6 desktop UI (main window, dialogs, preview)
  cli/                    # Command-line interface
  web/                    # Flask web server (API + static web interface)
  symbols/                # ezdxf electrical symbol definitions
config/                  # JSON libraries (circuits, modules, rules, valves,
                          # IO types, compressors, app config)
templates/               # DXF templates (controller, io, ladder,
                          # ladder_components, valves, templates)
web_interface/
  current/                # Active web frontend (circuit + compressor config)
  legacy/                 # Older frontend, kept for reference
docs/                    # Setup, CLI, and build guides
scripts/                 # Startup scripts and PyInstaller build script
test_data/               # Sample .aepj project files
```

## Getting started

### Prerequisites
- Python 3.9+ (add to PATH during install)

### Windows quick start
Double-click `scripts/START_APP.bat` (or run `scripts/START_APP.ps1`). It
creates a virtual environment, installs dependencies, and launches the GUI.
See [docs/SETUP_GUIDE.md](docs/SETUP_GUIDE.md) for details and troubleshooting.

### Manual setup
```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
python app.py
```

## Usage

### GUI mode (default)
```bash
python app.py
```

### CLI mode
```bash
# From a .aepj project file
python app.py --project my_project.aepj --output ./output [--format dxf|dwg|both]

# From an XNNOV Selection Tool JSON payload
python app.py --generate-from-selection selection.json --output ./output
```
Full reference: [docs/CLI_GUIDE.md](docs/CLI_GUIDE.md).

### Web interface
```bash
python src/web/web_server.py --host 127.0.0.1 --port 5000
```
Then open `http://127.0.0.1:5000/` to configure circuits/compressors and
generate drawings directly from the browser (downloads a ZIP of the
generated files). See [docs/WEB_CIRCUIT_COMPRESSOR_PLAN.md](docs/WEB_CIRCUIT_COMPRESSOR_PLAN.md)
for the design behind this feature.

### Building a standalone executable
```bash
python scripts/build_executable.py
```
See [docs/BUILD_EXECUTABLE.md](docs/BUILD_EXECUTABLE.md) for details.

## Configuration

Shared JSON libraries live under `config/`: circuit library, controller
modules, rules, valve types, IO types, and compressor library. These are
edited through the GUI (or the web interface, for compressors) and are
consumed by both the GUI and CLI/web generation paths.

## Documentation

- [docs/SETUP_GUIDE.md](docs/SETUP_GUIDE.md) — installation & troubleshooting
- [docs/CLI_GUIDE.md](docs/CLI_GUIDE.md) — CLI reference and examples
- [docs/CLI_IMPLEMENTATION_SUMMARY.md](docs/CLI_IMPLEMENTATION_SUMMARY.md) — CLI internals
- [docs/BUILD_EXECUTABLE.md](docs/BUILD_EXECUTABLE.md) — packaging with PyInstaller
- [docs/WEB_CIRCUIT_COMPRESSOR_PLAN.md](docs/WEB_CIRCUIT_COMPRESSOR_PLAN.md) — web configurator design/plan
