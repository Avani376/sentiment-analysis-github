"""Background dataset analysis jobs.

A dataset analysis scores every stored review with every selected model and
persists a Prediction row per (review, model). Jobs run on a daemon thread
with their own DB session; progress is written to the ``jobs`` table so the UI
can poll GET /api/v1/jobs/{id}.

Design notes:
* One running job per dataset is enforced at the API layer (409).
* Predictions are upserted per batch (delete + insert) so re-running a job
  refreshes scores with the same final state.
* Model loading happens inside the job thread — the API request returns
  immediately with 202.
"""

from __future__ import annotations

import logging
import threading
from datetime import UTC, datetime

from sqlalchemy import delete, insert, select

from app.db.session import SessionLocal
from app.models.entities import Job, Prediction, Review

logger = logging.getLogger(__name__)

BATCH_SIZE = 32


def _utcnow_naive() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def start_dataset_job(job_id: str) -> None:
    """Fire the job thread; returns immediately."""
    threading.Thread(target=_run_dataset_job, args=(job_id,), daemon=True).start()


def _run_dataset_job(job_id: str) -> None:
    with SessionLocal() as db:
        job = db.get(Job, job_id)
        if job is None:
            return
        job.status = "running"
        job.started_at = _utcnow_naive()
        db.commit()
        try:
            # Imported lazily: the registry pulls model adapters (and only
            # then torch/transformers) inside the worker thread.
            from app.services.registry import get_registry

            registry = get_registry()
            models = []
            for key in job.model_keys:
                model = registry.get(key)
                if model.is_enabled() and model.is_cached() is not False:
                    models.append(model)
                else:
                    logger.warning("Job %s: skipping unavailable model %s", job_id, key)

            review_ids = list(
                db.scalars(select(Review.id).where(Review.dataset_id == job.dataset_id)).all()
            )
            # emotion pass (separate task) included when enabled
            from app.services.emotion import get_emotion_analyzer

            emotion_analyzer = get_emotion_analyzer()
            include_emotion = emotion_analyzer.is_runnable()
            if not include_emotion:
                logger.warning(
                    "Job %s: emotion pass skipped (torch/transformers unavailable "
                    "or disabled) — sentiment predictions are unaffected", job_id)
            job.progress_total = len(review_ids) * (max(1, len(models)) + (1 if include_emotion else 0))
            job.progress_current = 0
            db.commit()

            done = 0
            for model in models:
                model._ensure_loaded()
                for offset in range(0, len(review_ids), BATCH_SIZE):
                    batch_ids = review_ids[offset : offset + BATCH_SIZE]
                    rows = db.scalars(select(Review).where(Review.id.in_(batch_ids))).all()
                    results = model.predict_batch([r.text for r in rows])

                    db.execute(
                        delete(Prediction).where(
                            Prediction.review_id.in_(batch_ids),
                            Prediction.model_key == model.metadata.key,
                        )
                    )
                    db.execute(
                        insert(Prediction),
                        [
                            {
                                "review_id": row.id,
                                "model_key": model.metadata.key,
                                "model_version": model.metadata.version,
                                "label": result.label,
                                "probabilities": result.probabilities,
                                "confidence": result.confidence,
                                "latency_ms": result.latency_ms / len(rows),
                            }
                            for row, result in zip(rows, results, strict=True)
                        ],
                    )
                    db.commit()
                    done += len(batch_ids)
                    job.progress_current = done
                    db.commit()

            if include_emotion:
                from app.api.v1.emotions import persist_dataset_emotions

                processed = persist_dataset_emotions(
                    db,
                    str(job.dataset_id),
                    emotion_analyzer.model_key,
                    emotion_analyzer.metadata_version,
                )
                done += processed
                job.progress_current = done
                db.commit()

            job.status = "succeeded"
            logger.info("Job %s succeeded (%d prediction passes)", job_id, done)
        except Exception as exc:  # noqa: BLE001 - job failures must be recorded
            db.rollback()
            job.status = "failed"
            job.error_message = f"{type(exc).__name__}: {exc}"[:500]
            logger.exception("Job %s failed", job_id)
        job.finished_at = _utcnow_naive()
        db.commit()
