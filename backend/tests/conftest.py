"""Test configuration.

Environment overrides are applied BEFORE any application import so the cached
settings singleton and the DB engine bind to a throwaway SQLite database.
"""

from __future__ import annotations

import os
import tempfile

_TMP = tempfile.mkdtemp(prefix="sentinex-test-")
os.environ["SENTINEX_DATABASE_URL"] = f"sqlite:///{_TMP}/test.db"
os.environ["SENTINEX_UPLOAD_DIR"] = f"{_TMP}/uploads"
os.environ["SENTINEX_ENABLE_DISTILBERT"] = "false"  # keeps tests hermetic & fast
os.environ["SENTINEX_MAX_UPLOAD_MB"] = "1"
os.environ["SENTINEX_LOG_LEVEL"] = "WARNING"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import delete  # noqa: E402

from app.db.base import Base  # noqa: E402
from app.db.session import SessionLocal, engine  # noqa: E402
from app.main import app as fastapi_app  # noqa: E402
from app.models.entities import Dataset, Job, Prediction, Review  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def _create_schema():
    Base.metadata.create_all(bind=engine)
    yield


@pytest.fixture(autouse=True)
def _clean_tables(_create_schema):
    yield
    with SessionLocal() as session:
        for model in (Prediction, Review, Job, Dataset):
            session.execute(delete(model))
        session.commit()


@pytest.fixture(scope="session")
def client() -> TestClient:
    return TestClient(fastapi_app)


@pytest.fixture
def csv_file():
    """Factory building multipart upload payloads."""

    def _make(
        content: str,
        filename: str = "reviews.csv",
        extra_fields: dict[str, str] | None = None,
    ) -> dict:
        files = {"file": (filename, content.encode("utf-8"), "text/csv")}
        if extra_fields:
            files.update(
                {k: (None, v) for k, v in extra_fields.items()}  # type: ignore[dict-item]
            )
        return files

    return _make
