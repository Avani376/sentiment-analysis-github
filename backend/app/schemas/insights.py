"""Schemas for aspect-based sentiment, topics, and business insights."""

from __future__ import annotations

from pydantic import BaseModel, Field


# --- ABSA (transparent rule-based baseline) ---------------------------------
class AspectMention(BaseModel):
    category: str
    term: str
    polarity: str
    confidence: float
    evidence: str = Field(description="Exact clause text the polarity came from.")
    review_id: int


class AspectAggregate(BaseModel):
    category: str
    mentions: int
    positive: int
    negative: int
    neutral: int
    avg_confidence: float
    positive_evidence: list[AspectMention]
    negative_evidence: list[AspectMention]


class AspectsOut(BaseModel):
    dataset_id: str
    method: str = Field(description="Honest description of the rule-based baseline.")
    clauses_analyzed: int
    aspects: list[AspectAggregate]


# --- Topic discovery ---------------------------------------------------------
class TopicOut(BaseModel):
    topic_id: int
    size: int
    keywords: list[str]
    sentiment: str | None = Field(description="Majority persisted prediction label, if available.")
    positive: int
    negative: int
    representative: list[dict]


class TopicsOut(BaseModel):
    dataset_id: str
    method: str
    adequate: bool
    message: str | None = None
    topics: list[TopicOut]


# --- Business insights --------------------------------------------------------
class InsightEvidence(BaseModel):
    statistic: str
    review_ids: list[int]


class InsightOut(BaseModel):
    id: str
    kind: str  # executive_summary | positive_theme | negative_theme | complaint | recommendation | topic
    title: str
    statement: str
    evidence: InsightEvidence
    strength: str  # strong | moderate | weak


class InsightsOut(BaseModel):
    dataset_id: str
    generated_from: list[str] = Field(description="Modules the insights were computed from.")
    insights: list[InsightOut]
