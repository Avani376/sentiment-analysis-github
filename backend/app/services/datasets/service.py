"""Dataset persistence: upload validation, storage, and row insertion."""

from __future__ import annotations

import uuid
from pathlib import Path

from fastapi import UploadFile
from sqlalchemy import delete, func, insert, select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.errors import NotFoundError, PayloadTooLargeError, UnprocessableError
from app.models.entities import Dataset, Review
from app.schemas.datasets import ReviewOut
from app.services.datasets.ingest import (
    ColumnMapping,
    IngestResult,
    ingest_frame,
    read_csv_with_fallback,
    resolve_mapping,
)

ALLOWED_SUFFIXES = {".csv"}


def validate_upload(file: UploadFile, settings: Settings) -> Path:
    """Persist an upload to the runtime dir after extension + size validation.

    The file is streamed to disk in chunks; nothing is loaded into memory
    wholesale. The stored name is server-generated — client-supplied names are
    kept only as metadata, never used as a path (path-traversal safety).
    """
    original_name = file.filename or "upload.csv"
    suffix = Path(original_name).suffix.lower()
    if suffix not in ALLOWED_SUFFIXES:
        raise UnprocessableError(
            "unsupported_file_type",
            "Only CSV files are supported.",
            {"received_suffix": suffix or None, "allowed": sorted(ALLOWED_SUFFIXES)},
        )

    settings.upload_dir.mkdir(parents=True, exist_ok=True)
    max_bytes = settings.max_upload_mb * 1024 * 1024
    destination = settings.upload_dir / f"upload_{uuid.uuid4().hex}.csv"

    written = 0
    with destination.open("wb") as out:
        while chunk := file.file.read(1024 * 1024):
            written += len(chunk)
            if written > max_bytes:
                out.close()
                destination.unlink(missing_ok=True)
                raise PayloadTooLargeError(
                    "upload_too_large",
                    f"Upload exceeds the {settings.max_upload_mb} MB limit.",
                    {"max_upload_mb": settings.max_upload_mb},
                )
            out.write(chunk)
    if written == 0:
        destination.unlink(missing_ok=True)
        raise UnprocessableError("empty_upload", "The uploaded file is empty.")
    return destination


def _to_review_out(review: Review) -> ReviewOut:
    return ReviewOut(
        id=review.id,
        external_id=review.external_id,
        text=review.text,
        label=review.label,
        raw_label=review.raw_label,
        review_timestamp=review.review_timestamp,
    )


def ingest_upload(
    db: Session,
    settings: Settings,
    *,
    file_path: Path,
    original_filename: str,
    display_name: str | None,
    requested_mapping: ColumnMapping | None,
) -> tuple[Dataset, list[ReviewOut]]:
    """Full pipeline: read -> map -> clean -> persist. Returns dataset + preview."""
    frame, encoding, warnings = read_csv_with_fallback(file_path, settings.max_upload_rows)
    mapping = resolve_mapping(frame, requested_mapping)
    result: IngestResult = ingest_frame(frame, mapping, settings.max_upload_rows)

    dataset = Dataset(
        name=display_name or Path(original_filename).stem,
        original_filename=original_filename,
        encoding=encoding,
        text_column=mapping.text,
        label_column=mapping.label,
        id_column=mapping.id,
        timestamp_column=mapping.timestamp,
        row_count=result.row_count,
        valid_rows=result.valid_rows,
        duplicate_rows=result.duplicate_rows,
        missing_text_rows=result.missing_text_rows,
        invalid_label_rows=result.invalid_label_rows,
        unparseable_timestamp_rows=result.unparseable_timestamp_rows,
        file_size_bytes=file_path.stat().st_size,
        ingest_warnings=warnings,
    )
    db.add(dataset)
    db.flush()  # assign dataset.id before inserting reviews

    if result.valid_rows:
        rows = [
            {
                "dataset_id": dataset.id,
                "external_id": external_id,
                "text": text,
                "label": label,
                "raw_label": raw_label,
                "review_timestamp": ts.to_pydatetime() if ts is not None else None,
            }
            for text, label, raw_label, external_id, ts in zip(
                result.text,
                result.labels,
                result.raw_labels,
                result.external_ids,
                result.timestamps,
                strict=True,
            )
        ]
        db.execute(insert(Review), rows)

    db.commit()
    preview = db.scalars(
        select(Review).where(Review.dataset_id == dataset.id).order_by(Review.id).limit(5)
    ).all()
    db.refresh(dataset)
    return dataset, [_to_review_out(r) for r in preview]


def get_dataset_or_404(db: Session, dataset_id: str) -> Dataset:
    dataset = db.get(Dataset, dataset_id)
    if dataset is None:
        raise NotFoundError("dataset_not_found", f"Dataset {dataset_id} does not exist.")
    return dataset


def list_reviews(
    db: Session,
    dataset: Dataset,
    *,
    q: str | None,
    label: str | None,
    page: int,
    page_size: int,
) -> tuple[list[ReviewOut], int]:
    """Paginated review listing with optional text search and label filter."""
    stmt = select(Review).where(Review.dataset_id == dataset.id)
    count_stmt = select(func.count(Review.id)).where(Review.dataset_id == dataset.id)
    if q:
        pattern = f"%{q}%"
        stmt = stmt.where(Review.text.ilike(pattern))
        count_stmt = count_stmt.where(Review.text.ilike(pattern))
    if label:
        stmt = stmt.where(Review.label == label)
        count_stmt = count_stmt.where(Review.label == label)

    total = db.scalar(count_stmt) or 0
    rows = db.scalars(
        stmt.order_by(Review.id).offset((page - 1) * page_size).limit(page_size)
    ).all()
    return [_to_review_out(r) for r in rows], total


def delete_dataset(db: Session, dataset: Dataset) -> None:
    """Cascade removes reviews and their predictions (FK ON DELETE CASCADE)."""
    db.execute(delete(Dataset).where(Dataset.id == dataset.id))
    db.commit()
