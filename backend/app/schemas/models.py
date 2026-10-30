"""Pydantic schemas for model registry endpoints."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class ModelCardOut(BaseModel):
    description: str
    intended_domain: str
    limitations: list[str]
    calibration: str
    training_provenance: str


class ModelOut(BaseModel):
    key: str
    display_name: str
    family: str
    version: str
    labels: list[str]
    supports_neutral: bool
    provenance: str = Field(
        description="trained_in_repo | legacy_artifact | pretrained_checkpoint"
    )
    source: str
    enabled: bool
    cached: bool | None = Field(description="Weights present locally; None = not applicable.")
    download_required: bool
    card: ModelCardOut | None


class EvaluationMetrics(BaseModel):
    accuracy: float | None = None
    precision: float | None = None
    recall: float | None = None
    f1_macro: float | None = None
    f1_weighted: float | None = None
    confusion_matrix: list[list[int]] | None = None
    per_class: dict[str, dict[str, float]] | None = None


class EvaluationOut(BaseModel):
    artifact: str
    model_key: str
    evaluation_type: str = Field(description="'reproduced' or 'historical_reference'.")
    created_at: datetime | None = None
    dataset: dict = Field(default_factory=dict)
    metrics: EvaluationMetrics = Field(default_factory=EvaluationMetrics)
    config: dict = Field(default_factory=dict)
    notes: str | None = None


class ModelCompareResponse(BaseModel):
    #: Every entry carries its own type + provenance; historical reference and
    #: reproduced results are never merged into one metric series by callers.
    evaluations: list[EvaluationOut]
