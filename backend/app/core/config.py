"""Centralized, environment-driven configuration for the SENTINEX AI backend.

Every runtime knob is exposed as a typed field with an environment override
(`SENTINEX_` prefix). No secrets are hardcoded; the optional LLM provider key
is read from the environment only and never logged.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

#: Repository root (backend/app/core/config.py -> backend/app -> backend -> repo).
PROJECT_ROOT = Path(__file__).resolve().parents[3]

BACKEND_ROOT = PROJECT_ROOT / "backend"
RUNTIME_DIR = BACKEND_ROOT / ".runtime"
ARTIFACTS_DIR = BACKEND_ROOT / "artifacts"


class Settings(BaseSettings):
    """Typed application settings loaded from the environment / `.env`."""

    model_config = SettingsConfigDict(
        env_prefix="SENTINEX_",
        env_file=(PROJECT_ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- Application -------------------------------------------------------
    app_name: str = "SENTINEX AI"
    app_version: str = "0.2.0"
    api_v1_prefix: str = "/api/v1"
    debug: bool = False
    log_level: str = "INFO"

    # --- CORS (frontend dev server) ----------------------------------------
    cors_origins: list[str] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ]

    # --- Storage ------------------------------------------------------------
    # SQLite is the zero-install development default; PostgreSQL is the
    # production target (see docker-compose.yml) and is enabled by setting
    # SENTINEX_DATABASE_URL, e.g. postgresql+psycopg://user:pass@host/db.
    database_url: str = f"sqlite:///{(RUNTIME_DIR / 'sentinex.db').as_posix()}"
    upload_dir: Path = RUNTIME_DIR / "uploads"
    max_upload_mb: int = 10
    max_upload_rows: int = 100_000

    # --- Inference ----------------------------------------------------------
    #: Max texts accepted by the synchronous batch endpoint. Larger workloads
    #: go through dataset-level background jobs (Milestone 4).
    batch_limit: int = 100
    max_text_chars: int = 20_000

    #: Heavy transformer toggles. DistilBERT uses the local HF cache when
    #: present; cardiffnlp downloads ~500 MB on first use, so it is off by
    #: default (audit constraint: disk-constrained machine).
    enable_distilbert: bool = True
    enable_cardiffnlp: bool = False

    # --- Artifact locations -------------------------------------------------
    legacy_model_path: Path = PROJECT_ROOT / "models" / "tfidf_logreg.pkl"
    imdb_model_path: Path = ARTIFACTS_DIR / "models" / "tfidf_logreg_imdb_v1.pkl"
    model_cards_dir: Path = ARTIFACTS_DIR / "model_cards"
    evaluations_dir: Path = ARTIFACTS_DIR / "evaluations"

    def ensure_runtime_dirs(self) -> None:
        """Create runtime directories that must exist before serving traffic."""
        self.upload_dir.mkdir(parents=True, exist_ok=True)
        RUNTIME_DIR.mkdir(parents=True, exist_ok=True)


@lru_cache
def get_settings() -> Settings:
    """Return the cached settings singleton used across the application."""
    return Settings()
