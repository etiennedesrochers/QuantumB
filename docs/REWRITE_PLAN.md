# QuantumB Rewrite Plan — Service Layer + FastAPI + New Web UI

Goal: replace the monolithic app with a small, layered system while leaving the
current GUI/CLI/old web server untouched (frozen as legacy).

Decisions (2026-09-04):
- Backend API: **FastAPI**
- Frontend: **vanilla JS (ES modules, no build step)**
- Legacy (everything under `legacy_code_interface/`): **frozen — do not modify**
- New code lives in a root `quantumb/` package (not `src/`, which would collide
  on `sys.path` with `legacy_code_interface/src`). `quantumb/legacy_bridge.py`
  puts `legacy_code_interface/` on `sys.path` so `import src.core...` keeps
  resolving to the frozen engine.

## Status

- Phase 0 — **skipped by decision** (no golden tests).
- Phase 1 — **done**: `quantumb/services/`.
- Phase 2 — **done**: `quantumb/api/` (FastAPI, `/docs` live).
- Phase 3 — **done**: `web_ui/` served at `/`.
- Phase 4 — **done**: parity verified, legacy web stack deprecated.
- Phase 5 — optional, not started.

## Why

- The bloat is the desktop GUI (~5,700 lines: `main_window.py` 3.9k, `dialogs.py` 1.8k).
- The core engine (`src/core/`, ~2k lines) is already small and reusable.
- The old web server never calls the core directly — it writes a temp JSON and
  runs `app.py --generate-from-selection` in a `subprocess`. There is no real
  Python API today. This plan creates one.

## Target architecture

```
web_ui/                       NEW vanilla-JS frontend (static files)
    │  HTTP/JSON
quantumb/api/                 NEW FastAPI app = "python interface"
    │  plain function calls (no subprocess)
quantumb/services/            NEW façade = "python package to get information"
    │  wraps the managers below
legacy_code_interface/src/    EXISTING engine (core + symbols), frozen
legacy_code_interface/config|templates|data_excel
                              EXISTING data — single source of truth old + new
```

- `quantumb/services/` — plain Python functions returning plain dicts/dataclasses.
  No Flask, no FastAPI, no PySide6 imports. This is the importable "package".
- `quantumb/api/` — thin HTTP layer: Pydantic request/response models, routes
  that delegate to `quantumb/services/`. Nothing else.
- `web_ui/` — static SPA served by FastAPI's StaticFiles. No CORS needed
  (same origin).

## Phase 0 — Baseline safety net — SKIPPED

Golden-output tests were deliberately skipped; parity is checked manually in
Phase 4 instead.

## Phase 1 — Service layer (`quantumb/services/`) — DONE

Modules, each thin over existing managers:

| Module | Wraps | Functions (shape) |
|---|---|---|
| `template_service.py` | `template_manager` | `list_templates() -> dict[str, list[str]]`, `list_templates_for(category)` |
| `compressor_service.py` | `compressor_manager`, `workbook_manager` | `list/get/create/update/delete_compressor()`, `import/export_compressors()`, `sync_from_workbook()`, `attach_library_templates()` |
| `library_service.py` | `circuit_library`, `module_manager`, `rules_manager`, `valve_manager`, `app_config` + raw config JSON | `list_circuits()`, `list_modules()`, `list_io_types()`, `list_ladder_types()`, `list_rules()`, `list_valve_types()`, ... |
| `workbook_service.py` | `workbook_manager` | `load_table_catalog()`, `load_compressor_rows()`, `load_generator_filters(mfr)`, `load_circuits_for_selection(...)` |
| `generation_service.py` | `selection_adapter` + `cli.CLIGenerator` (**in-process**) | `generate_from_selection(payload, fmt) -> GenerationResult`, `generated_archive()` ctx manager |

Rules:
- Services accept/return plain dicts; they own path constants already defined
  in core (do not duplicate `Path(__file__)...` logic).
- No edits to legacy files. Generation instantiates the existing `CLIGenerator`
  rather than extracting code out of `cli.py`.
- Errors raise typed exceptions (`ServiceError`, `NotFoundError`,
  `ValidationError`, `GenerationError`) that Phase 2 maps to HTTP codes.

Deviation from legacy: each generation runs in a fresh temp dir (no shared
`web_interface/current/output`), and the temp `.aepj` is kept out of the ZIP.

## Phase 2 — FastAPI app (`quantumb/api/`) — DONE

```
quantumb/api/
  main.py          # create_app(): routers + error handlers + StaticFiles(web_ui)
  models.py        # Pydantic schemas (SelectionPayload, Compressor, ...)
  routes/
    templates.py   # GET  /api/templates[/{category}]
    compressors.py # GET/POST/PUT/DELETE /api/compressors[...] + import/export/sync-workbook
    libraries.py   # GET  /api/circuits|modules|io-types|ladder-types|rules|valve-types|app-config
    workbook.py    # GET  /api/workbook/tables|compressors|generator-filters|circuits
    generate.py    # POST /api/generate?format=dxf|dwg|both -> ZIP (FileResponse)
```

- Endpoint shapes mirror the old server for easy frontend comparison; OpenAPI
  docs come free at `/docs`.
- Generation runs in-process via `generation_service` in a threadpool
  (sync `def` endpoint) — ezdxf work is CPU-bound.
- ZIP built in a temp dir, returned with `FileResponse`, cleaned up by a
  `BackgroundTask` after the response is sent.
- Run: `scripts/START_API.ps1` (or `python -m quantumb.api.main --port 8000`).
- `ServiceError` subclasses map to 400/404/500 via a single exception handler.
- `web_ui/` is mounted at `/` only once the folder exists.

## Phase 3 — New web UI (`web_ui/`) — DONE

Vanilla ES modules, no build step, hash routing (`#/generator`, `#/compressors`,
`#/libraries`) so StaticFiles never has to handle unknown paths:

```
web_ui/
  index.html
  css/main.css
  js/
    main.js           # hash router + theme toggle
    api.js            # the ONLY file that knows URLs
    dom.js            # el()/fillSelect()/downloadBlob()/withBusy() helpers
    state.js          # tiny cache (compressors, templates)
    components/       # toast.js (toasts + promise-based confirm), table.js
    pages/
      generator.js    # workbook selection -> circuit preview -> POST /api/generate
      compressors.js  # compressor CRUD, template scopes, sync/import/export
      libraries.js    # read-only browsers for the config libraries
```

- No `localStorage` except the light/dark theme preference.
- `alert()`/`confirm()` replaced by toasts and a promise-based modal.
- All DOM is built with `el()` (textContent), so workbook/config values are
  never injected as HTML.
- Improvement over legacy: project name/number/revision/drawn-by and the output
  format are real inputs instead of hardcoded constants.

## Phase 4 — Parity check & cutover — DONE

`scripts/parity_check.py` starts the legacy Flask server (`:5000`) and the new
FastAPI server (`:8000`), then:

1. Diffs the JSON of every shared GET endpoint (`/api/templates`,
   `/api/compressors`, the four `/api/workbook/*` routes).
2. Pulls a real workbook selection, expands it into a selection payload the
   same way the UI does, POSTs it to both `/api/generate` implementations and
   diffs the ZIP member list + per-file sizes.

Result: **all endpoints identical, generated DWG byte-size identical.**

Two legacy-only ZIP artifacts are excluded from the diff because the new server
intentionally drops them: `_temp_selection.aepj` (internal temp project) and a
nested `generated_drawings.zip` (the legacy server zips its output directory
into itself). The legacy output dir is cleared before its run since it is
reused across requests.

Cutover: `scripts/START_API.*` is the entry point; the root `README.md` marks
`legacy_code_interface/src/web/web_server.py`, `web_interface/` and
`START_WEB_SERVER.*` as deprecated — **the files stay in place** and the GUI and
CLI are untouched.

## Phase 5 (later, optional) — Real packaging

- Add `pyproject.toml`: package `quantumb` (services + api), console script
  `quantumb-api`.
- Only attempt after Phases 1–4 are stable; requires care not to break the
  frozen legacy imports (`from src.core...`).

## Risks / gotchas

- **Don't move `legacy_code_interface/src`** — GUI/CLI import it via
  `from src.core...`; moving files breaks them. `quantumb/legacy_bridge.py`
  is the only place that knows this path.
- **Never create a root `src/`** — it would shadow the legacy `src` package.
- **Config JSON is shared state**: old and new systems read/write the same
  `legacy_code_interface/config/*.json`. Fine for single-user; add file-locking
  only if concurrent writes become real.
- **`workbook_manager` reads the `.xlsm`** — keep it lazy/cached so API
  responses stay fast.
- Generation timeout: old server used a 120 s subprocess timeout; in-process
  calls have no natural timeout — probably fine for single-user desktop use.
- Known pre-existing limitation (from compressor work): "regular"-type
  compressor templates resolve to empty pages because `CLIGenerator` only
  loads `LADDER_TEMPLATES_DIR`. Out of scope here; fix separately later.

## Milestones

1. ~~M1: Phase 0 + 1 — services~~ **done** (Phase 0 skipped).
2. ~~M2: Phase 2 — FastAPI serving all endpoints; generate works~~ **done**.
3. ~~M3: Phase 3 — new UI for generator + compressors + libraries~~ **done**.
4. ~~M4: Phase 4 — parity verified, cutover, docs updated~~ **done**.
