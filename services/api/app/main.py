"""FastAPI application. Routers are registered once here (bootstrap); do not edit per sprint.

- app.routes.system   — /health, /v1/readiness, /v1/collections (Zoro)
- app.routes.sessions — /v1/sessions/... (Zoro)
- app.voice.router    — voice binding + webhook (Luffy)
"""
from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.errors import register_error_handlers
from app.fixtures import get_fixture_bundle
from app.routes import sessions, system
from app.voice import router as voice

API_TITLE = "Dermatology Case Navigator API"
API_VERSION = "1.0.0"


def create_app() -> FastAPI:
    settings = get_settings()
    get_fixture_bundle()  # fail fast if shared fixtures do not validate
    app = FastAPI(
        title=API_TITLE,
        version=API_VERSION,
        description="Fictional-demo consultation preparation API. No diagnosis or treatment recommendation.",
        separate_input_output_schemas=False,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["GET", "POST"],
        allow_headers=["Authorization", "Content-Type", "X-Demo-Access-Code"],
    )
    register_error_handlers(app)
    app.include_router(system.router)
    app.include_router(sessions.router)
    app.include_router(voice.router)
    return app


app = create_app()
