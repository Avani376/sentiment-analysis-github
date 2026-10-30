"""SQLAlchemy ORM entities.

Primary keys: UUIDs for user-facing resources (datasets, jobs); compact integer
keys for high-volume rows (reviews, predictions). Model binaries and uploaded
CSV files stay on the filesystem — never inside the database.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import (
    JSON,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


def _utcnow() -> datetime:
    return datetime.now(UTC)


def new_uuid() -> str:
    return str(uuid.uuid4())


#: JSON that maps to JSONB on PostgreSQL and plain JSON on SQLite.
JsonType = JSON().with_variant(JSONB(), "postgresql")


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, nullable=False)


class Dataset(TimestampMixin, Base):
    """An uploaded review dataset with ingestion statistics."""

    __tablename__ = "datasets"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    encoding: Mapped[str] = mapped_column(String(32), nullable=False, default="utf-8")

    # Column mapping chosen explicitly or auto-detected at ingest time.
    text_column: Mapped[str] = mapped_column(String(255), nullable=False)
    label_column: Mapped[str | None] = mapped_column(String(255), nullable=True)
    id_column: Mapped[str | None] = mapped_column(String(255), nullable=True)
    timestamp_column: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Ingestion statistics — the honest record of what happened to the upload.
    row_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    valid_rows: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    duplicate_rows: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    missing_text_rows: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    invalid_label_rows: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    unparseable_timestamp_rows: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    file_size_bytes: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    ingest_warnings: Mapped[list] = mapped_column(JsonType, nullable=False, default=list)

    reviews: Mapped[list[Review]] = relationship(
        back_populates="dataset", cascade="all, delete-orphan", passive_deletes=True
    )


class Review(TimestampMixin, Base):
    """A single review row kept from an uploaded dataset."""

    __tablename__ = "reviews"
    __table_args__ = (Index("ix_reviews_dataset_label", "dataset_id", "label"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    dataset_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("datasets.id", ondelete="CASCADE"), nullable=False, index=True
    )
    external_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    #: Normalized ground-truth label when the upload supplied one: positive | negative.
    label: Mapped[str | None] = mapped_column(String(16), nullable=True)
    #: The value exactly as it appeared in the CSV (for traceability).
    raw_label: Mapped[str | None] = mapped_column(String(64), nullable=True)
    review_timestamp: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    dataset: Mapped[Dataset] = relationship(back_populates="reviews")
    predictions: Mapped[list[Prediction]] = relationship(
        back_populates="review", cascade="all, delete-orphan", passive_deletes=True
    )


class Prediction(TimestampMixin, Base):
    """A persisted model prediction for a dataset review."""

    __tablename__ = "predictions"
    __table_args__ = (UniqueConstraint("review_id", "model_key", name="uq_predictions_review_model"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    review_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("reviews.id", ondelete="CASCADE"), nullable=False, index=True
    )
    model_key: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    model_version: Mapped[str] = mapped_column(String(64), nullable=False)
    #: Normalized predicted label: positive | negative | neutral.
    label: Mapped[str] = mapped_column(String(16), nullable=False)
    #: Full probability distribution over the model's supported labels.
    probabilities: Mapped[dict] = mapped_column(JsonType, nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    latency_ms: Mapped[float] = mapped_column(Float, nullable=False)

    review: Mapped[Review] = relationship(back_populates="predictions")


class Job(TimestampMixin, Base):
    """Background job record (dataset batch analysis — Milestone 4 runner)."""

    __tablename__ = "jobs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    dataset_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("datasets.id", ondelete="CASCADE"), nullable=True, index=True
    )
    job_type: Mapped[str] = mapped_column(String(64), nullable=False)
    #: queued | running | succeeded | failed | cancelled
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="queued", index=True)
    progress_current: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    progress_total: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    model_keys: Mapped[list] = mapped_column(JsonType, nullable=False, default=list)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
