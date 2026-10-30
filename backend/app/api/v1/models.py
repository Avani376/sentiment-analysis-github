"""Model registry endpoints: listing, cards, and evaluation comparison."""

from __future__ import annotations

import json

from fastapi import APIRouter

from app.api.deps import RegistryDep, SettingsDep
from app.core.errors import NotFoundError
from app.schemas.models import (
    EvaluationMetrics,
    EvaluationOut,
    ModelCardOut,
    ModelCompareResponse,
    ModelOut,
)

router = APIRouter(prefix="/models", tags=["models"])


def _model_out(registry: RegistryDep, key: str) -> ModelOut:
    model = registry.get(key)
    card = model.load_card()
    meta = model.metadata
    cached = model.is_cached()
    return ModelOut(
        key=meta.key,
        display_name=meta.display_name,
        family=meta.family,
        version=meta.version,
        labels=list(meta.labels),
        supports_neutral=meta.supports_neutral,
        provenance=meta.provenance,
        source=meta.source,
        enabled=model.is_enabled(),
        cached=cached,
        download_required=model.download_required,
        card=ModelCardOut(
            description=card.description,
            intended_domain=card.intended_domain,
            limitations=card.limitations,
            calibration=card.calibration,
            training_provenance=card.training_provenance,
        ),
    )


@router.get("", response_model=list[ModelOut])
def list_models(registry: RegistryDep) -> list[ModelOut]:
    """Every registered model with availability; no weights are loaded here."""
    return [_model_out(registry, key) for key in registry.keys()]


@router.get("/compare", response_model=ModelCompareResponse)
def compare_models(settings: SettingsDep) -> ModelCompareResponse:
    """All saved evaluation artifacts.

    Each artifact carries its own ``evaluation_type``: ``reproduced`` (generated
    by backend/ml/evaluate.py against a documented held-out split) or
    ``historical_reference`` (committed numbers whose pipeline is absent).
    Callers must keep the two visually separate.
    """
    evaluations: list[EvaluationOut] = []
    if settings.evaluations_dir.is_dir():
        for path in sorted(settings.evaluations_dir.glob("*.json")):
            try:
                raw = json.loads(path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                continue  # a malformed artifact must not break the listing
            metrics = raw.get("metrics", {})
            evaluations.append(
                EvaluationOut(
                    artifact=path.name,
                    model_key=raw.get("model_key", path.stem),
                    evaluation_type=raw.get("evaluation_type", "reproduced"),
                    created_at=raw.get("created_at"),
                    dataset=raw.get("dataset", {}),
                    metrics=EvaluationMetrics(**metrics),
                    config=raw.get("config", {}),
                    notes=raw.get("notes"),
                )
            )
    evaluations.sort(key=lambda e: (e.evaluation_type, e.artifact))
    return ModelCompareResponse(evaluations=evaluations)


@router.get("/{model_key}", response_model=ModelOut)
def get_model(model_key: str, registry: RegistryDep) -> ModelOut:
    try:
        return _model_out(registry, model_key)
    except NotFoundError:
        raise
    except Exception as exc:  # pragma: no cover - defensive
        raise NotFoundError("model_not_found", f"Unknown model key {model_key!r}.") from exc
