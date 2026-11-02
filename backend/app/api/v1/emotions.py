"""Emotion intelligence endpoints — separate task from sentiment, by design."""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel, Field
from sqlalchemy import delete, insert, select
from sqlalchemy.orm import Session

from app.api.deps import DbSession, SettingsDep
from app.core.errors import ServiceUnavailableError, UnprocessableError
from app.models.entities import EmotionResult, Review
from app.schemas.datasets import ReviewOut
from app.services.datasets.service import get_dataset_or_404
from app.services.emotion import EMOTION_PRESENTATION, get_emotion_analyzer

router = APIRouter(prefix="/emotions", tags=["emotions"])


class EmotionRequest(BaseModel):
    text: str = Field(min_length=1)
    texts: list[str] | None = Field(default=None, max_length=100)


class EmotionOut(BaseModel):
    model_key: str
    model_version: str
    emotions: dict[str, float]
    dominant_emotion: str
    confidence: float
    latency_ms: float
    presentation: dict[str, str] = Field(
        description="Canonical label -> product-facing name (approximate mapping)."
    )


class EmotionBatchResponse(BaseModel):
    results: list[EmotionOut]
    batch_latency_ms: float


class EmotionDistribution(BaseModel):
    emotion: str
    presentation: str
    count: int
    share: float


class EmotionExample(ReviewOut):
    dominant_emotion: str
    confidence: float


class DatasetEmotionAnalytics(BaseModel):
    dataset_id: str
    total_reviews: int
    analyzed_reviews: int
    has_results: bool
    model_key: str
    distribution: list[EmotionDistribution]
    examples: dict[str, list[EmotionExample]]


def _analyze_texts(analyzer, texts: list[str]) -> tuple[list[EmotionOut], float]:
    predictions = analyzer.predict_batch(texts)
    return [
        EmotionOut(
            model_key=analyzer.model_key,
            model_version=analyzer.metadata_version,
            emotions=p.emotions,
            dominant_emotion=p.dominant_emotion,
            confidence=p.confidence,
            latency_ms=p.latency_ms,
            presentation=EMOTION_PRESENTATION,
        )
        for p in predictions
    ], predictions[-1].latency_ms if predictions else 0.0


@router.post("/analyze", response_model=EmotionBatchResponse)
def analyze_emotions(payload: EmotionRequest, settings: SettingsDep) -> EmotionBatchResponse:
    """Ad-hoc emotion classification (no persistence — dataset jobs persist)."""
    analyzer = get_emotion_analyzer()
    if not analyzer.is_enabled():
        raise ServiceUnavailableError(
            "emotion_disabled", "Emotion model is disabled by configuration."
        )
    texts = [payload.text.strip()]
    if payload.texts:
        if any(not t.strip() for t in payload.texts):
            raise UnprocessableError("empty_text_in_batch", "Every batch item needs text.")
        texts = [t.strip() for t in payload.texts]
    if len(texts) > 100:
        raise UnprocessableError("batch_limit_exceeded", "Maximum 100 texts per request.")
    try:
        results, latency = _analyze_texts(analyzer, texts)
    except Exception as exc:  # noqa: BLE001 - download/network failures surface cleanly
        raise ServiceUnavailableError(
            "emotion_model_unavailable",
            f"Emotion model could not be loaded (first use downloads ~330 MB): {type(exc).__name__}",
        ) from exc
    return EmotionBatchResponse(results=results, batch_latency_ms=round(latency, 3))


@router.get("/datasets/{dataset_id}", response_model=DatasetEmotionAnalytics)
def dataset_emotions(dataset_id: str, db: DbSession) -> DatasetEmotionAnalytics:
    """Persisted emotion distribution for a dataset (populated by analysis jobs)."""
    dataset = get_dataset_or_404(db, dataset_id)
    results = db.execute(
        select(EmotionResult, Review)
        .join(Review, EmotionResult.review_id == Review.id)
        .where(Review.dataset_id == dataset.id)
    ).all()

    distribution: dict[str, int] = {}
    examples: dict[str, list[EmotionExample]] = {}
    model_key = "emotion_distilroberta"
    for emotion_result, review in results:
        model_key = emotion_result.model_key
        dominant = emotion_result.dominant_emotion
        distribution[dominant] = distribution.get(dominant, 0) + 1
        bucket = examples.setdefault(dominant, [])
        if len(bucket) < 3:
            bucket.append(
                EmotionExample(
                    id=review.id,
                    external_id=review.external_id,
                    text=review.text,
                    label=review.label,
                    raw_label=review.raw_label,
                    review_timestamp=review.review_timestamp,
                    dominant_emotion=dominant,
                    confidence=emotion_result.confidence,
                )
            )

    total = sum(distribution.values())
    return DatasetEmotionAnalytics(
        dataset_id=dataset.id,
        total_reviews=dataset.valid_rows,
        analyzed_reviews=total,
        has_results=total > 0,
        model_key=model_key,
        distribution=[
            EmotionDistribution(
                emotion=emotion,
                presentation=EMOTION_PRESENTATION.get(emotion, emotion),
                count=count,
                share=round(count / total, 4),
            )
            for emotion, count in sorted(distribution.items(), key=lambda kv: -kv[1])
        ],
        examples=examples,
    )


def persist_dataset_emotions(db: Session, dataset_id: str, model_key: str, model_version: str) -> int:
    """Score every review of a dataset with the emotion model and persist.

    Used by the analysis job; returns the number of reviews processed.
    """
    analyzer = get_emotion_analyzer()
    analyzer._ensure_loaded()
    review_ids = list(
        db.scalars(select(Review.id).where(Review.dataset_id == dataset_id)).all()
    )
    db.execute(
        delete(EmotionResult).where(EmotionResult.review_id.in_(review_ids or [-1]))
    )
    db.commit()
    processed = 0
    for offset in range(0, len(review_ids), 32):
        batch = db.scalars(select(Review).where(Review.id.in_(review_ids[offset : offset + 32]))).all()
        predictions = analyzer.predict_batch([r.text for r in batch])
        db.execute(
            insert(EmotionResult),
            [
                {
                    "review_id": review.id,
                    "model_key": model_key,
                    "model_version": model_version,
                    "emotions": prediction.emotions,
                    "dominant_emotion": prediction.dominant_emotion,
                    "confidence": prediction.confidence,
                    "latency_ms": prediction.latency_ms,
                }
                for review, prediction in zip(batch, predictions, strict=True)
            ],
        )
        db.commit()
        processed += len(batch)
    return processed
