"""Job endpoints: launch dataset analysis, poll progress."""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter
from pydantic import BaseModel, Field
from sqlalchemy import select

from app.api.deps import AuthUser, DbSession, RegistryDep
from app.core.errors import ConflictError, NotFoundError, UnprocessableError
from app.models.entities import Job
from app.services.datasets.service import get_dataset_or_404
from app.services.jobs import start_dataset_job

router = APIRouter(tags=["jobs"])


class AnalyzeDatasetRequest(BaseModel):
    """Model keys to score with; defaults to every available cached model."""

    models: list[str] | None = Field(default=None, max_length=10)


class JobOut(BaseModel):
    id: str
    dataset_id: str | None
    job_type: str
    status: str
    progress_current: int
    progress_total: int
    model_keys: list[str]
    error_message: str | None
    started_at: datetime | None
    finished_at: datetime | None
    created_at: datetime


def _job_out(job: Job) -> JobOut:
    return JobOut(
        id=job.id,
        dataset_id=job.dataset_id,
        job_type=job.job_type,
        status=job.status,
        progress_current=job.progress_current,
        progress_total=job.progress_total,
        model_keys=job.model_keys,
        error_message=job.error_message,
        started_at=job.started_at,
        finished_at=job.finished_at,
        created_at=job.created_at,
    )


@router.post("/datasets/{dataset_id}/analyze", status_code=202)
def analyze_dataset(
    dataset_id: str,
    db: DbSession,
    registry: RegistryDep,
    user: AuthUser,
    payload: AnalyzeDatasetRequest | None = None,
) -> JobOut:
    """Queue background analysis of every review in the dataset (login required)."""
    dataset = get_dataset_or_404(db, dataset_id)

    running = db.scalar(
        select(Job.id)
        .where(
            Job.dataset_id == dataset_id,
            Job.job_type == "dataset_analysis",
            Job.status.in_(("queued", "running")),
        )
        .order_by(Job.created_at.desc())
    )
    if running:
        raise ConflictError(
            "job_already_running",
            "An analysis job is already queued or running for this dataset.",
            {"job_id": running},
        )

    if payload and payload.models:
        for key in payload.models:
            registry.ensure_usable(key)
        keys = payload.models
    else:
        keys = [
            key
            for key in registry.keys()
            if registry.get(key).is_enabled() and registry.get(key).is_cached() is not False
        ]
    if not keys:
        raise UnprocessableError(
            "no_models_available",
            "No cached models are available to run this analysis.",
        )
    if dataset.valid_rows == 0:
        raise UnprocessableError("empty_dataset", "This dataset has no review rows to analyze.")

    job = Job(dataset_id=dataset.id, job_type="dataset_analysis", model_keys=keys)
    db.add(job)
    db.commit()
    db.refresh(job)
    start_dataset_job(job.id)
    return _job_out(job)


@router.get("/jobs/{job_id}", response_model=JobOut)
def get_job(job_id: str, db: DbSession) -> JobOut:
    job = db.get(Job, job_id)
    if job is None:
        raise NotFoundError("job_not_found", f"Job {job_id} does not exist.")
    return _job_out(job)
