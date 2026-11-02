"""Vercel serverless entrypoint for the SENTINEX AI FastAPI application.

Exposes ``app`` for the @vercel/python runtime (ServerlessASGI). The backend
package lives in ``backend/`` and is added to ``sys.path`` here.

Serverless constraints handled:
* Filesystem is ephemeral and only /tmp is writable -> DATABASE_URL and
  UPLOAD_DIR are overridden in vercel.json to /tmp paths.
* Alembic cannot run as a build step against a per-instance SQLite file, so
  tables are created idempotently on cold start (SENTINEX_AUTO_CREATE_TABLES).
* DistilBERT is disabled by configuration (250 MB function limit); the two
  TF-IDF models cover the deployed demo.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1] / "backend"
sys.path.insert(0, str(BACKEND_DIR))

# The @vercel/python runtime looks for this module-level ``app`` symbol — the
# import is intentionally "unused" in Python terms. Never remove it.
from app.main import app  # noqa: E402, F401  (FastAPI ASGI application)

from app.core.config import get_settings  # noqa: E402

_settings = get_settings()
_settings.ensure_runtime_dirs()

if os.environ.get("SENTINEX_AUTO_CREATE_TABLES", "false").lower() == "true":
    # Idempotent cold-start schema bootstrap for ephemeral serverless DBs.
    from app.db.base import Base
    from app.db.session import engine

    Base.metadata.create_all(bind=engine)
