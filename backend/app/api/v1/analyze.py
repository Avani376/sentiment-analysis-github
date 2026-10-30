"""Analysis endpoints: single and batch sentiment inference.

Ad-hoc requests are not persisted; dataset-level analysis (persisted
predictions, background jobs) arrives with the bulk pipeline in Milestone 4.
"""

from __future__ import annotations

from fastapi import APIRouter

from app.api.deps import RegistryDep, SettingsDep
from app.core.errors import UnprocessableError
from app.schemas.analyze import (
    BatchAnalyzeRequest,
    BatchAnalyzeResponse,
    BatchPredictionOut,
    PredictionOut,
    SingleAnalyzeRequest,
    SingleAnalyzeResponse,
)
from app.services.registry import SentimentModel

router = APIRouter(prefix="/analyze", tags=["analyze"])


def _resolve_models(registry: RegistryDep, keys: list[str] | None, settings: SettingsDep) -> list[SentimentModel]:
    """Explicit keys are enforced (404/503 on failure); default = cached+enabled."""
    if keys:
        return [registry.ensure_usable(key) for key in keys]
    default = [
        registry.get(key)
        for key in registry.keys()
        if registry.get(key).is_enabled() and registry.get(key).is_cached() is not False
    ]
    if not default:
        raise UnprocessableError(
            "no_models_available",
            "No models are currently available. Request a model key explicitly to trigger its load.",
        )
    return default


def _prediction_out(model: SentimentModel, result, *, text_index: int | None = None, per_item_ms: float | None = None) -> PredictionOut | BatchPredictionOut:
    base = dict(
        model_key=model.metadata.key,
        model_version=model.metadata.version,
        model_display_name=model.metadata.display_name,
        label=result.label,
        probabilities=result.probabilities,
        confidence=result.confidence,
        latency_ms=round(per_item_ms if per_item_ms is not None else result.latency_ms, 3),
        supports_neutral=model.metadata.supports_neutral,
    )
    if text_index is None:
        return PredictionOut(**base)
    return BatchPredictionOut(**base, text_index=text_index)


@router.post("/single", response_model=SingleAnalyzeResponse)
def analyze_single(payload: SingleAnalyzeRequest, registry: RegistryDep, settings: SettingsDep) -> SingleAnalyzeResponse:
    text = payload.text.strip()
    if not text:
        raise UnprocessableError("empty_text", "Review text must not be blank.")
    if len(text) > settings.max_text_chars:
        raise UnprocessableError(
            "text_too_long",
            f"Review text exceeds the {settings.max_text_chars} character limit.",
            {"max_text_chars": settings.max_text_chars, "received": len(text)},
        )

    models = _resolve_models(registry, payload.models, settings)
    predictions = [
        _prediction_out(model, model.predict_single(text)) for model in models
    ]
    return SingleAnalyzeResponse(text_chars=len(text), predictions=predictions)


@router.post("/batch", response_model=BatchAnalyzeResponse)
def analyze_batch(payload: BatchAnalyzeRequest, registry: RegistryDep, settings: SettingsDep) -> BatchAnalyzeResponse:
    texts = [t.strip() for t in payload.texts]
    if any(not t for t in texts):
        raise UnprocessableError(
            "empty_text_in_batch", "Every batch item must contain review text."
        )
    if len(texts) > settings.batch_limit:
        raise UnprocessableError(
            "batch_limit_exceeded",
            f"Batch size {len(texts)} exceeds the synchronous limit of {settings.batch_limit}. "
            "Upload a dataset for large-scale analysis.",
            {"batch_limit": settings.batch_limit},
        )

    models = _resolve_models(registry, payload.models, settings)
    out: list[BatchPredictionOut] = []
    batch_latency_ms = 0.0
    for model in models:
        results = model.predict_batch(texts)
        batch_latency_ms += max((r.latency_ms for r in results), default=0.0)
        n = len(texts)
        for i, result in enumerate(results):
            out.append(
                _prediction_out(  # type: ignore[arg-type, return-value]
                    model,
                    result,
                    text_index=i,
                    per_item_ms=result.latency_ms / n,
                )
            )
    return BatchAnalyzeResponse(count=len(texts), batch_latency_ms=round(batch_latency_ms, 3), predictions=out)
