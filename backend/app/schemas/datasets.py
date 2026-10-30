"""Pydantic schemas for dataset management endpoints."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class DatasetIngestStats(BaseModel):
    row_count: int
    valid_rows: int
    duplicate_rows: int
    missing_text_rows: int
    invalid_label_rows: int
    unparseable_timestamp_rows: int


class DatasetOut(BaseModel):
    id: str
    name: str
    original_filename: str
    encoding: str
    text_column: str
    label_column: str | None
    id_column: str | None
    timestamp_column: str | None
    stats: DatasetIngestStats
    file_size_bytes: int
    ingest_warnings: list[str]
    created_at: datetime


class DatasetCreatedResponse(DatasetOut):
    preview: list[ReviewOut] = Field(description="First rows of the stored dataset.")


class ReviewOut(BaseModel):
    id: int
    external_id: str | None
    text: str
    label: str | None
    raw_label: str | None
    review_timestamp: datetime | None


class ReviewPage(BaseModel):
    items: list[ReviewOut]
    total: int
    page: int
    page_size: int
    pages: int


class ReviewQuery(BaseModel):
    q: str | None = Field(default=None, max_length=200, description="Case-insensitive text search.")
    label: str | None = Field(default=None, pattern="^(positive|negative)$")
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=100)
