"""FastAPI application: thin HTTP layer over `quantumb.services`."""

from __future__ import annotations

import logging
import os
from datetime import datetime
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from ..legacy_bridge import REPO_ROOT
from ..services.errors import NotFoundError, ServiceError, ValidationError
from .models import HealthResponse
from .routes import compressors, generate, libraries, projects, templates, workbook

logger = logging.getLogger(__name__)

WEB_UI_DIR = REPO_ROOT / "web_ui"

# The Express front end runs on another port, so it needs explicit CORS.
DEFAULT_CORS_ORIGINS = (
    "http://127.0.0.1:3000",
    "http://localhost:3000",
)

_STATUS_BY_ERROR = {
    NotFoundError: 404,
    ValidationError: 400,
}


def _cors_origins() -> list[str]:
    configured = os.environ.get("QUANTUMB_CORS_ORIGINS", "")
    origins = [origin.strip() for origin in configured.split(",") if origin.strip()]
    return origins or list(DEFAULT_CORS_ORIGINS)


def create_app() -> FastAPI:
    app = FastAPI(
        title="QuantumB API",
        version="0.1.0",
        summary="Drawing generation and library access for the QuantumB selection tool.",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=_cors_origins(),
        allow_methods=["GET", "POST", "PUT", "DELETE"],
        allow_headers=["Content-Type"],
    )

    @app.exception_handler(ServiceError)
    async def handle_service_error(request: Request, exc: ServiceError) -> JSONResponse:
        status_code = _STATUS_BY_ERROR.get(type(exc), 500)
        if status_code >= 500:
            logger.exception("Service error on %s", request.url.path, exc_info=exc)
        return JSONResponse(status_code=status_code, content={"error": str(exc)})

    @app.get("/api/health", tags=["health"])
    def health() -> HealthResponse:
        return HealthResponse(
            status="ok",
            service="QuantumB API",
            timestamp=datetime.now().isoformat(),
        )

    for module in (templates, libraries, workbook, compressors, generate, projects):
        app.include_router(module.router)

    # Registered last: without it the StaticFiles mount answers unknown /api
    # paths, reporting 405 on POST instead of a plain 404.
    @app.api_route(
        "/api/{path:path}",
        methods=["GET", "POST", "PUT", "DELETE"],
        include_in_schema=False,
    )
    def unknown_api(path: str) -> JSONResponse:
        return JSONResponse(
            status_code=404, content={"error": f"Unknown API endpoint: /api/{path}"}
        )

    _mount_web_ui(app)
    return app


def _mount_web_ui(app: FastAPI) -> None:
    """Serve the new SPA at `/` once `web_ui/` exists (Phase 3)."""
    if not WEB_UI_DIR.is_dir():
        return
    app.mount("/", StaticFiles(directory=str(WEB_UI_DIR), html=True), name="web_ui")


app = create_app()


def main() -> None:
    import argparse

    import uvicorn

    parser = argparse.ArgumentParser(description="QuantumB API server")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--reload", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO)
    uvicorn.run(
        "quantumb.api.main:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
        app_dir=str(Path(REPO_ROOT)),
    )


if __name__ == "__main__":
    main()
