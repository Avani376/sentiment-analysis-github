"""SENTINEX AI backend — FastAPI application factory."""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.api.v1 import api_router
from app.core.config import get_settings
from app.core.errors import register_exception_handlers
from app.core.logging import configure_logging
from app.db.session import engine
from app.services.registry import get_registry

description = """
SENTINEX AI — Review Intelligence Platform.

Transform unstructured customer reviews into measurable, explainable,
evidence-grounded intelligence: multi-model sentiment, emotion detection,
aspect-based analysis, topic discovery, and reproducible model evaluation.

Every model in the registry declares its own label mapping and limitations —
binary models are never forced to emit a neutral class, and confidence scores
are never presented as calibrated probabilities.
"""


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    settings.ensure_runtime_dirs()
    get_registry()  # build the registry eagerly so /models is always consistent
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(settings.log_level)

    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description=description,
        lifespan=lifespan,
    )

    if settings.cors_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=settings.cors_origins,
            allow_credentials=False,
            allow_methods=["GET", "POST", "DELETE"],
            allow_headers=["*"],
        )

    register_exception_handlers(app)
    app.include_router(api_router, prefix=settings.api_v1_prefix)

    @app.get("/health", tags=["ops"])
    def health() -> dict:
        """Liveness + readiness snapshot: database reachability and registry size."""
        try:
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            database = "ok"
        except Exception:  # noqa: BLE001 - health must never raise
            database = "unreachable"
        return {
            "status": "ok",
            "app": settings.app_name,
            "version": settings.app_version,
            "database": database,
            "registered_models": len(get_registry().keys()),
        }

    return app


app = create_app()
