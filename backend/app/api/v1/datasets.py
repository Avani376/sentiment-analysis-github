"""Dataset management endpoints: upload, inspect, explore, delete."""

from __future__ import annotations

import csv
import io
from typing import Annotated

from fastapi import APIRouter, File, Form, Query, Response, UploadFile
from sqlalchemy import select

from app.api.deps import AuthUser, DbSession, SettingsDep
from app.core.errors import UnprocessableError
from app.models.entities import Dataset, Prediction, Review
from app.schemas.analytics import DatasetAnalytics
from app.schemas.datasets import (
    DatasetCreatedResponse,
    DatasetIngestStats,
    DatasetOut,
    ReviewPage,
)
from app.services.analytics import dataset_analytics
from app.services.datasets.ingest import ColumnMapping
from app.services.datasets.service import (
    delete_dataset,
    get_dataset_or_404,
    ingest_upload,
    list_reviews,
    validate_upload,
)

router = APIRouter(prefix="/datasets", tags=["datasets"])


def _dataset_out(dataset: Dataset) -> DatasetOut:
    return DatasetOut(
        id=dataset.id,
        name=dataset.name,
        original_filename=dataset.original_filename,
        encoding=dataset.encoding,
        text_column=dataset.text_column,
        label_column=dataset.label_column,
        id_column=dataset.id_column,
        timestamp_column=dataset.timestamp_column,
        stats=DatasetIngestStats(
            row_count=dataset.row_count,
            valid_rows=dataset.valid_rows,
            duplicate_rows=dataset.duplicate_rows,
            missing_text_rows=dataset.missing_text_rows,
            invalid_label_rows=dataset.invalid_label_rows,
            unparseable_timestamp_rows=dataset.unparseable_timestamp_rows,
        ),
        file_size_bytes=dataset.file_size_bytes,
        ingest_warnings=dataset.ingest_warnings,
        created_at=dataset.created_at,
    )


@router.post("/upload", response_model=DatasetCreatedResponse, status_code=201)
def upload_dataset(
    db: DbSession,
    settings: SettingsDep,
    user: AuthUser,
    file: Annotated[UploadFile, File(description="CSV file with review rows.")],
    name: Annotated[str | None, Form(max_length=255)] = None,
    text_column: Annotated[str | None, Form()] = None,
    label_column: Annotated[str | None, Form()] = None,
    id_column: Annotated[str | None, Form()] = None,
    timestamp_column: Annotated[str | None, Form()] = None,
) -> DatasetCreatedResponse:
    """Upload a CSV of reviews.

    Column mapping is optional; anything not supplied is auto-detected with
    conservative heuristics and reported back in the response so the caller
    can verify what was chosen.
    """
    file_path = validate_upload(file, settings)

    mapping_fields = (text_column, label_column, id_column, timestamp_column)
    if text_column is None and any(field and field.strip() for field in mapping_fields):
        raise UnprocessableError(
            "incomplete_mapping",
            "Column mapping must include text_column when any other column is specified.",
        )

    requested = None
    if text_column is not None:
        if not text_column.strip():
            raise UnprocessableError("invalid_mapping", "text_column must be a non-empty name.")
        requested = ColumnMapping(
            text=text_column.strip(),
            label=(label_column.strip() or None) if label_column else None,
            id=(id_column.strip() or None) if id_column else None,
            timestamp=(timestamp_column.strip() or None) if timestamp_column else None,
        )

    dataset, preview = ingest_upload(
        db,
        settings,
        file_path=file_path,
        original_filename=file.filename or "upload.csv",
        display_name=name,
        requested_mapping=requested,
    )
    return DatasetCreatedResponse(**_dataset_out(dataset).model_dump(), preview=preview)


@router.get("", response_model=list[DatasetOut])
def list_datasets(
    db: DbSession,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> list[DatasetOut]:
    stmt = (
        select(Dataset)
        .order_by(Dataset.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    return [_dataset_out(d) for d in db.scalars(stmt).all()]


@router.get("/{dataset_id}", response_model=DatasetOut)
def get_dataset(dataset_id: str, db: DbSession) -> DatasetOut:
    return _dataset_out(get_dataset_or_404(db, dataset_id))


@router.get("/{dataset_id}/reviews", response_model=ReviewPage)
def get_dataset_reviews(
    dataset_id: str,
    db: DbSession,
    q: Annotated[str | None, Query(max_length=200)] = None,
    label: Annotated[str | None, Query(pattern="^(positive|negative)$")] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> ReviewPage:
    dataset = get_dataset_or_404(db, dataset_id)
    items, total = list_reviews(db, dataset, q=q, label=label, page=page, page_size=page_size)
    return ReviewPage(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        pages=(total + page_size - 1) // page_size,
    )


@router.delete("/{dataset_id}", status_code=204)
def remove_dataset(dataset_id: str, db: DbSession, user: AuthUser) -> None:
    dataset = get_dataset_or_404(db, dataset_id)
    delete_dataset(db, dataset)


@router.get("/{dataset_id}/analytics", response_model=DatasetAnalytics)
def get_dataset_analytics(dataset_id: str, db: DbSession) -> DatasetAnalytics:
    """Aggregated model results for this dataset (empty state until a job ran)."""
    dataset = get_dataset_or_404(db, dataset_id)
    return dataset_analytics(db, dataset)


@router.get("/{dataset_id}/export")
def export_dataset(dataset_id: str, db: DbSession) -> Response:
    """Download reviews + persisted predictions as CSV."""
    dataset = get_dataset_or_404(db, dataset_id)
    reviews = db.scalars(
        select(Review).where(Review.dataset_id == dataset.id).order_by(Review.id)
    ).all()
    predictions = db.execute(
        select(Prediction).join(Review, Prediction.review_id == Review.id).where(
            Review.dataset_id == dataset.id
        )
    ).scalars().all()

    by_review: dict[int, list[Prediction]] = {}
    for pred in predictions:
        by_review.setdefault(pred.review_id, []).append(pred)
    model_keys = sorted({p.model_key for p in predictions})

    buffer = io.StringIO()
    writer = csv.writer(buffer)
    header = ["review_id", "external_id", "text", "ground_truth_label", "timestamp"]
    header += [f"{key}_label" for key in model_keys]
    header += [f"{key}_confidence" for key in model_keys]
    writer.writerow(header)
    for review in reviews:
        row = [
            review.id,
            review.external_id or "",
            review.text,
            review.label or "",
            review.review_timestamp.isoformat() if review.review_timestamp else "",
        ]
        preds = {p.model_key: p for p in by_review.get(review.id, [])}
        row += [preds[key].label if key in preds else "" for key in model_keys]
        row += [preds[key].confidence if key in preds else "" for key in model_keys]
        writer.writerow(row)

    filename = "".join(ch if ch.isalnum() else "-" for ch in dataset.name).strip("-") or "dataset"
    return Response(
        content=buffer.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}-export.csv"'},
    )
