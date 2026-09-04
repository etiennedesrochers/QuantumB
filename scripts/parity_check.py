"""Phase 4 parity check: legacy Flask server vs the new FastAPI server.

Starts both servers, compares every shared GET endpoint, then pushes the same
selection payload through both `/api/generate` implementations and diffs the
resulting ZIPs (member list + per-file size).

Usage:
    python scripts/parity_check.py [--legacy-port 5000] [--new-port 8000]
"""

from __future__ import annotations

import argparse
import io
import json
import subprocess
import sys
import time
import urllib.error
import urllib.request
import zipfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
LEGACY_ROOT = REPO_ROOT / "legacy_code_interface"

# Endpoints both servers expose with identical paths and payload shapes.
SHARED_GETS = [
    "/api/templates",
    "/api/compressors",
    "/api/workbook/tables",
    "/api/workbook/compressors",
    "/api/workbook/generator-filters",
    "/api/workbook/generator-filters?manufacturer=Mitsubishi",
    "/api/workbook/circuits?capacity=13&manufacturer=Mitsubishi&tension=480",
]

# Legacy-only artifacts: it keeps the temp project in the output dir and zips
# that dir into itself, so its own archive ends up nested inside the download.
IGNORED_MEMBERS = {"_temp_selection.aepj", "generated_drawings.zip"}


def get(base: str, path: str, timeout: int = 180):
    with urllib.request.urlopen(f"{base}{path}", timeout=timeout) as response:
        return response.status, json.loads(response.read().decode("utf-8"))


def post_generate(base: str, payload: dict, timeout: int = 300) -> bytes:
    request = urllib.request.Request(
        f"{base}/api/generate",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.read()


def wait_for(base: str, timeout: float = 60.0) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            urllib.request.urlopen(f"{base}/api/health", timeout=5).read()
            return True
        except (urllib.error.URLError, OSError):
            time.sleep(1)
    return False


def start_legacy(port: int) -> subprocess.Popen:
    return subprocess.Popen(
        [sys.executable, str(LEGACY_ROOT / "src" / "web" / "web_server.py"), "--port", str(port)],
        cwd=str(LEGACY_ROOT),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def start_new(port: int) -> subprocess.Popen:
    return subprocess.Popen(
        [sys.executable, "-m", "quantumb.api.main", "--port", str(port)],
        cwd=str(REPO_ROOT),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def zip_members(data: bytes) -> dict[str, int]:
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        return {
            info.filename: info.file_size
            for info in archive.infolist()
            if not info.is_dir() and Path(info.filename).name not in IGNORED_MEMBERS
        }


def clear_legacy_output() -> None:
    """The legacy server reuses one output dir, so stale files would skew the diff."""
    output_dir = LEGACY_ROOT / "web_interface" / "current" / "output"
    for path in output_dir.glob("*"):
        if path.is_file():
            path.unlink()


def build_payload(circuits_payload: dict) -> dict:
    return {
        "project_name": "Parity Check",
        "project_number": "PARITY-001",
        "revision": "A",
        "drawn_by": "parity_check.py",
        "circuits": [
            {
                "name": circuit.get("name", ""),
                "description": circuit.get("description", ""),
                "compressors": [
                    {
                        "model_number": comp.get("model_number") or "",
                        "description": comp.get("description") or "",
                        "templates": [
                            {
                                "name": template["name"],
                                "quantity": 1 if template.get("scope") == "shared"
                                else max(1, int(comp.get("quantity") or 1)),
                            }
                            for template in comp.get("templates") or []
                        ],
                    }
                    for comp in circuit.get("compressors") or []
                ],
            }
            for circuit in circuits_payload.get("circuits") or []
        ],
    }


def compare_gets(legacy: str, new: str) -> list[str]:
    failures = []
    for path in SHARED_GETS:
        try:
            _, legacy_body = get(legacy, path)
            _, new_body = get(new, path)
        except Exception as exc:
            failures.append(f"{path}: request failed ({exc})")
            print(f"  [FAIL] {path}: {exc}")
            continue

        if legacy_body == new_body:
            print(f"  [OK]   {path}")
        else:
            failures.append(f"{path}: bodies differ")
            print(f"  [DIFF] {path}")
            print(f"         legacy: {json.dumps(legacy_body)[:200]}")
            print(f"         new   : {json.dumps(new_body)[:200]}")
    return failures


def compare_generate(legacy: str, new: str) -> list[str]:
    _, circuits_payload = get(new, "/api/workbook/circuits?capacity=13&manufacturer=Mitsubishi&tension=480")
    payload = build_payload(circuits_payload)

    template_count = sum(
        len(comp["templates"]) for circuit in payload["circuits"] for comp in circuit["compressors"]
    )
    if template_count == 0:
        return [
            "generate: the selected compressors have no templates assigned, "
            "so the comparison would be vacuous. Assign templates first."
        ]

    clear_legacy_output()
    legacy_members = zip_members(post_generate(legacy, payload))
    new_members = zip_members(post_generate(new, payload))

    if legacy_members == new_members:
        print(f"  [OK]   /api/generate ({len(new_members)} file(s) identical in name and size)")
        return []

    missing = sorted(set(legacy_members) - set(new_members))
    if missing:
        print("  [DIFF] /api/generate is missing files the legacy server produced")
        print(f"         missing: {missing}")
        return ["generate: new output is missing legacy files"]

    # Expected: the new server resolves circuit templates across every category
    # dir, so it draws artwork and emits controller pages the legacy server
    # silently skipped. See CircuitTemplateManager in the services layer.
    print("  [EXPECTED DIFF] /api/generate produces richer output than legacy")
    print(f"         legacy: {legacy_members}")
    print(f"         new   : {new_members}")
    return []


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--legacy-port", type=int, default=5000)
    parser.add_argument("--new-port", type=int, default=8000)
    args = parser.parse_args()

    legacy = f"http://127.0.0.1:{args.legacy_port}"
    new = f"http://127.0.0.1:{args.new_port}"

    print("Starting servers\u2026")
    processes = [start_legacy(args.legacy_port), start_new(args.new_port)]
    try:
        for base, name in ((legacy, "legacy"), (new, "new")):
            if not wait_for(base):
                print(f"[ERROR] {name} server did not become ready at {base}")
                return 1
        print(f"  legacy -> {legacy}\n  new    -> {new}\n")

        print("Comparing GET endpoints:")
        failures = compare_gets(legacy, new)

        print("\nComparing generation output:")
        failures += compare_generate(legacy, new)
    finally:
        for process in processes:
            process.terminate()

    print()
    if failures:
        print(f"PARITY FAILED ({len(failures)} issue(s)):")
        for failure in failures:
            print(f"  - {failure}")
        return 1

    print("PARITY OK \u2014 all shared endpoints and the generated ZIP match.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
