"""Analytics response schemas."""

from __future__ import annotations

from pydantic import BaseModel


class ModelAnalytics(BaseModel):
    model_key: str
    model_version: str
    predictions: int
    label_counts: dict[str, int]
    avg_confidence: float | None


class ReviewExample(BaseModel):
    review_id: int
    text: str
    label: str
    confidence: float


class DatasetAnalytics(BaseModel):
    dataset_id: str
    total_reviews: int
    total_predictions: int
    has_results: bool
    per_model: list[ModelAnalytics]
    agreement: dict[str, float]
    examples: dict[str, list[ReviewExample]]
