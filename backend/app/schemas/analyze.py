"""Pydantic schemas for the analyze endpoints."""

from __future__ import annotations

from pydantic import BaseModel, Field


class SingleAnalyzeRequest(BaseModel):
    text: str = Field(min_length=1, description="Review text to analyze.")
    #: Model registry keys; defaults to every available model.
    models: list[str] | None = Field(default=None, max_length=10)


class BatchAnalyzeRequest(BaseModel):
    texts: list[str] = Field(min_length=1, description="1..batch_limit review texts.")
    models: list[str] | None = Field(default=None, max_length=10)


class PredictionOut(BaseModel):
    model_key: str
    model_version: str
    model_display_name: str
    label: str = Field(description="Normalized label: positive | negative | neutral.")
    probabilities: dict[str, float] = Field(
        description="Probability per label the model supports. Binary models never include neutral."
    )
    confidence: float = Field(description="Predicted-class probability (not calibrated across models).")
    latency_ms: float
    supports_neutral: bool


class SingleAnalyzeResponse(BaseModel):
    text_chars: int = Field(description="Length of the analyzed text; the text itself is not echoed.")
    predictions: list[PredictionOut]


class BatchPredictionOut(PredictionOut):
    text_index: int


class BatchAnalyzeResponse(BaseModel):
    count: int
    batch_latency_ms: float
    predictions: list[BatchPredictionOut]
