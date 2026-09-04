# QuantumB

Generates AutoCAD electrical drawings (DXF/DWG) for XNNOV refrigeration
circuits from an Excel workbook + a shared compressor/template library.

## Layout

| Path | What it is |
|---|---|
| `quantumb/services/` | Plain-Python facade over the drawing engine. No web/GUI imports. |
| `quantumb/api/` | FastAPI app — thin HTTP layer over the services. |
| `node_app/` | Express + EJS front end (`:3000`), calls the API at `:8000`. |
| `web_ui/` | Previous vanilla-JS SPA, still served by FastAPI at `/`. Kept until `node_app/` reaches parity. |
| `order_file/IO_Order.xlsx` | I/O ordering workbook — one sheet per machine type. |
| `legacy_code_interface/` | **Frozen** original app: PySide6 GUI, CLI, Flask server, old web UI, and the shared engine (`src/core`), config JSON, DXF templates and the Excel workbook. |
| `scripts/` | `START_WEB.*` (both servers), `START_API.*`, `parity_check.py`, `build_order_file.py`. |
| `docs/REWRITE_PLAN.md` | The rewrite plan and its current status. |

`quantumb/legacy_bridge.py` is the only module that knows where the legacy code
lives; it puts `legacy_code_interface/` on `sys.path` so the engine keeps
importing as `src.core.*`. Do not create a top-level `src/` — it would shadow
that package.

## Running

```powershell
pip install -r requirements.txt
scripts\START_WEB.ps1            # API on :8000 + web UI on http://127.0.0.1:3000
```

Or run the two halves separately:

```powershell
scripts\START_API.ps1            # http://127.0.0.1:8000  (API docs at /docs)
cd node_app; npm install; npm start
```

The browser calls the API cross-origin, so the API only accepts the origins in
`QUANTUMB_CORS_ORIGINS` (default `http://127.0.0.1:3000,http://localhost:3000`).
Point the front end elsewhere with `API_BASE`, and change its port with `PORT`.

Config, templates and the workbook are read from `legacy_code_interface/`
(`config/`, `templates/`, `data_excel/`) — shared with the legacy app.

## I/O ordering workbook

`order_file/IO_Order.xlsx` decides the order of the I/O list and which I/O is
always present. One sheet per machine type (`Regular`, `AHU`, …) — adding a
type means adding a sheet. Columns:

| Column | Meaning |
|---|---|
| `Section` | `front` (machine I/O before the circuits), `circuit` (block repeated per circuit), `back` (machine I/O after them) |
| `Direction` | `Input` or `Output` |
| `Order` | position within its section + direction |
| `Label` | tag; in `circuit` rows `#` is replaced by the circuit number |
| `IOType` | name from `config/io_types_library.json` |
| `Description` | optional; blank becomes `Reserved` |

Entries the circuit templates do not produce are injected as `Reserved`
placeholders, so each machine type has its own I/O count. Selecting
“No ordering” in the UI skips the workbook entirely.

`scripts/build_order_file.py` regenerates the workbook from the legacy
`Order_IO.xlsx` (refuses to overwrite without `--force`).

## Deprecated

The Flask server (`legacy_code_interface/src/web/web_server.py`), its frontend
(`legacy_code_interface/web_interface/`) and
`legacy_code_interface/scripts/START_WEB_SERVER.*` are superseded by the
FastAPI app. They still work and are kept for reference; the desktop GUI
(`legacy_code_interface/app.py`) and the CLI are unaffected.

`scripts/parity_check.py` starts both servers and verifies that every shared
endpoint and the generated ZIP still match.
