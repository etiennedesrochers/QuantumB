# Plan: Web Circuit/Compressor Configurator with Shared vs Per-Unit Templates

**TL;DR**: Extend the existing (partially-built) "New Web interface" pages — `base.html` (circuit config) and `config_compressor.html` (compressor/template config) — into a working end-to-end flow: define compressor types with Shared vs Per-Unit templates in a shared server-side library, pick # circuits + compressor + quantity per circuit, and generate drawings directly via the existing `/api/generate` → `CLIGenerator` → drawing pipeline.

**Key discovery**: Much of this already exists but is disconnected/buggy — `web_server.py`'s static folder points at the wrong directory (`Web Interface` instead of `New Web interface`), the compressor library only lives in browser `localStorage`, template pickers use hardcoded placeholder names instead of real files on disk, there's no Shared-vs-Per-Unit concept, and clicking "Generate" only downloads a JSON file with manual CLI instructions instead of calling the already-working `/api/generate` endpoint.

## Steps

### Phase 1 — Backend data & API foundation
1. New `compressor_manager.py` (mirrors `module_manager.py`): `load_compressors()`/`save_compressors()` against new `compressor_library.json`. Schema: `{id, name, model, manufacturer, capacity, templates: [{type, name, scope}]}` where `scope` is `"shared"` or `"per_unit"`.
2. Add `list_templates()` helper to `template_manager.py` reusing its existing `*_TEMPLATES_DIR` constants.
3. Fix `WEB_INTERFACE_DIR` in `web_server.py` to point at `New Web interface`.
4. Add routes: `GET/POST /api/compressors`, `GET /api/templates`, `GET /api/compressors/export`, `POST /api/compressors/import`.

### Phase 2 — Config Compressor page (depends on Phase 1)
5. Swap `localStorage` calls for `fetch('/api/compressors')` in `script.js`.
6. Load template dropdowns from `/api/templates` instead of `compressor_config.json`.
7. Add a Shared/Per-Unit **Scope** selector to the Add Template form; persist/display it.
8. Add Excel export/import buttons (bonus, JSON stays primary).

### Phase 3 — Circuit Generator page (depends on Phase 1 & 2)
9. Await compressor fetch before generating circuit rows.
10. Rewrite `handleFormSubmit()` to build the nested schema `selection_adapter.py` already expects, expanding per-unit templates to `quantity = circuit qty` and shared templates to `quantity = 1`.
11. Replace "download JSON + run CLI manually" with a direct POST to `/api/generate`, downloading the returned ZIP.

### Phase 4 — Verification
1. Confirm pages load with corrected static path.
2. Create a compressor with mixed shared/per-unit templates; confirm persistence across reloads.
3. Generate a circuit (3x compressor) and download the ZIP.
4. Inspect `selection_arguments.json` in the ZIP to confirm per-unit template appears 3x and shared template 1x.
5. Confirm DXFs are present in the output.

## Relevant files
- `compressor_manager.py` — new
- `template_manager.py` — add `list_templates()`
- `web_server.py` — fix static path, add new routes
- `config_compressor.html`, `script.js`, `base.html` (all in `New Web interface/`) — frontend rewiring
- `selection_adapter.py`, `models.py`, `cli.py` — reference only, no changes needed

## Decisions
- Server-side shared JSON library (not localStorage).
- One compressor type + quantity per circuit (no multi-type circuits yet).
- Shared/Per-Unit is a per-template `scope` flag, expanded client-side into existing `{name, quantity}` schema — no backend model changes.
- Template lists sourced live from disk via new API, not hardcoded JSON.
- Excel is a bonus; JSON is primary.

## Further considerations
1. `/api/generate` temp-dir cleanup remains a no-op — out of scope unless it becomes an issue.
2. Voltage/Application/Fan Manufacturer/Vapor Injection fields collected in the form aren't wired into generation — left as-is unless you want them used.
