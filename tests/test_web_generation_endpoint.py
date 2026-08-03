import importlib
import os
import sys
from pathlib import Path

import pytest


@pytest.fixture
def web_app(monkeypatch, tmp_path):
    monkeypatch.setenv("PYTHONPATH", str(Path(__file__).resolve().parents[1]))
    sys.modules.pop("src.web.web_server", None)
    module = importlib.import_module("src.web.web_server")
    return module.app


def test_generate_endpoint_runs_cli_generator(monkeypatch, tmp_path, web_app):
    calls = {}

    def fake_run_cli_generator(selection_json, output_dir):
        calls["selection_json"] = selection_json
        calls["output_dir"] = output_dir
        return True, "ok"

    monkeypatch.setattr("src.web.web_server.run_cli_generator", fake_run_cli_generator)

    client = web_app.test_client()
    response = client.post(
        "/api/generate",
        json={
            "project_name": "Test",
            "project_number": "001",
            "revision": "A",
            "drawn_by": "User",
            "circuits": [{"name": "CU001", "compressors": []}],
        },
    )

    assert response.status_code == 200
    assert response.mimetype == "application/zip"
    assert response.headers["Content-Disposition"].startswith("attachment")
    assert calls["selection_json"]["project_name"] == "Test"
    assert os.path.normpath(calls["output_dir"]).endswith(
        os.path.normpath("web_interface/current/output")
    )
