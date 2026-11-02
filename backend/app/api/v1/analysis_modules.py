"""Analysis-module endpoints: aspects, topics, insights (computed on demand)."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Query

from app.api.deps import DbSession
from app.schemas.insights import AspectsOut, InsightsOut, TopicsOut
from app.services.absa import dataset_aspects
from app.services.datasets.service import get_dataset_or_404
from app.services.insights import dataset_insights
from app.services.topics import dataset_topics

router = APIRouter(tags=["analysis-modules"])


@router.get("/datasets/{dataset_id}/aspects", response_model=AspectsOut)
def get_dataset_aspects(dataset_id: str, db: DbSession) -> AspectsOut:
    """Aspect mentions with clause-level polarity and evidence spans.

    Transparent rule-based baseline — the response carries the method note.
    """
    dataset = get_dataset_or_404(db, dataset_id)
    return dataset_aspects(db, dataset)


@router.get("/datasets/{dataset_id}/topics", response_model=TopicsOut)
def get_dataset_topics(
    dataset_id: str,
    db: DbSession,
    k: Annotated[int | None, Query(ge=2, le=10)] = None,
) -> TopicsOut:
    """TF-IDF + KMeans topic clusters (seeded; graceful on small datasets)."""
    dataset = get_dataset_or_404(db, dataset_id)
    return dataset_topics(db, dataset, k)


@router.get("/datasets/{dataset_id}/insights", response_model=InsightsOut)
def get_dataset_insights(dataset_id: str, db: DbSession) -> InsightsOut:
    """Evidence-grounded business insights — every claim cites reviews/stats."""
    dataset = get_dataset_or_404(db, dataset_id)
    return dataset_insights(db, dataset)
