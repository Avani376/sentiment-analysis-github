"""Business insights — deterministic, evidence-grounded generation.

Every insight cites a computed statistic and/or concrete review IDs. No LLM is
involved: claims are template-assembled from measured values (analytics,
aspects, topics). Observed facts and suggested actions are kept in separate
insight kinds so nothing pretends to be more than it is.
"""

from __future__ import annotations

import math

from sqlalchemy.orm import Session

from app.schemas.insights import InsightEvidence, InsightOut, InsightsOut
from app.services.absa import dataset_aspects
from app.services.analytics import dataset_analytics
from app.services.topics import dataset_topics


def _strength(sample_size: int, min_confidence: float = 0.0) -> str:
    if sample_size >= 5 and min_confidence >= 0.75:
        return "strong"
    if sample_size >= 2:
        return "moderate"
    return "weak"


def dataset_insights(db: Session, dataset) -> InsightsOut:
    analytics = dataset_analytics(db, dataset)
    aspects = dataset_aspects(db, dataset)
    topics = dataset_topics(db, dataset, None)

    insights: list[InsightOut] = []
    primary = analytics.per_model[0] if analytics.per_model else None

    # --- executive summary ---------------------------------------------------
    if primary is not None:
        pos = primary.label_counts.get("positive", 0)
        neg = primary.label_counts.get("negative", 0)
        total = primary.predictions or 1
        dominant = "positive" if pos >= neg else "negative"
        share = round(max(pos, neg) / total * 100, 1)
        statement = (
            f"{analytics.total_reviews} reviews were scored by {len(analytics.per_model)} models. "
            f"The primary model ({primary.model_key}) reads the dataset as {dominant}: "
            f"{max(pos, neg)}/{total} reviews ({share}%), average confidence {primary.avg_confidence}."
        )
        insights.append(
            InsightOut(
                id="executive-summary",
                kind="executive_summary",
                title="Executive summary",
                statement=statement,
                evidence=InsightEvidence(
                    statistic=f"{primary.predictions} predictions · avg confidence {primary.avg_confidence}",
                    review_ids=[],
                ),
                strength="strong" if primary.predictions >= 20 else "moderate",
            )
        )
        if analytics.agreement:
            pair, value = next(iter(analytics.agreement.items()))
            insights.append(
                InsightOut(
                    id="model-agreement",
                    kind="executive_summary",
                    title="Model agreement",
                    statement=(
                        f"Models {pair.replace(' | ', ' and ')} assign the same sentiment to "
                        f"{value * 100:.0f}% of shared reviews. {100 - value * 100:.0f}% disagreement "
                        "means individual scores should not be treated as ground truth."
                    ),
                    evidence=InsightEvidence(statistic=f"{value}", review_ids=[]),
                    strength="strong" if value >= 0.8 else "moderate",
                )
            )

    # --- aspect themes ---------------------------------------------------------
    for aspect in aspects.aspects:
        if aspect.mentions < 2:
            continue  # one mention is an anecdote, not a theme
        polarity = "positive" if aspect.positive >= aspect.negative else "negative"
        kind = "positive_theme" if polarity == "positive" else "negative_theme"
        citations = [m.review_id for m in (aspect.positive_evidence + aspect.negative_evidence)[:3]]
        insights.append(
            InsightOut(
                id=f"aspect-{aspect.category}",
                kind=kind,
                title=f"{aspect.category.capitalize()}: customers are {polarity}",
                statement=(
                    f"{aspect.mentions} mentions of '{aspect.category}' — {aspect.positive} positive, "
                    f"{aspect.negative} negative (avg clause confidence {aspect.avg_confidence})."
                ),
                evidence=InsightEvidence(
                    statistic=f"{aspect.positive}↑ / {aspect.negative}↓ of {aspect.mentions}",
                    review_ids=citations,
                ),
                strength=_strength(aspect.mentions, aspect.avg_confidence),
            )
        )
        if polarity == "negative" and aspect.mentions >= 2:
            worst = aspect.negative_evidence[0] if aspect.negative_evidence else None
            insights.append(
                InsightOut(
                    id=f"complaint-{aspect.category}",
                    kind="complaint",
                    title=f"Recurring complaint: {aspect.category}",
                    statement=(
                        f"'{aspect.category}' appears in {aspect.negative} negative clauses. "
                        + (f"Example: \"{worst.evidence}\"" if worst else "")
                    ),
                    evidence=InsightEvidence(
                        statistic=f"{aspect.negative} negative of {aspect.mentions} mentions",
                        review_ids=[m.review_id for m in aspect.negative_evidence[:3]],
                    ),
                    strength=_strength(aspect.negative, aspect.avg_confidence),
                )
            )
            insights.append(
                InsightOut(
                    id=f"recommendation-{aspect.category}",
                    kind="recommendation",
                    title=f"Suggested action: investigate {aspect.category}",
                    statement=(
                        f"Review the {aspect.negative} negative '{aspect.category}' mentions with the "
                        "product team. This is a data-suggested action — validate against the cited "
                        "reviews before acting."
                    ),
                    evidence=InsightEvidence(
                        statistic=f"{aspect.negative} negative mentions",
                        review_ids=[m.review_id for m in aspect.negative_evidence[:3]],
                    ),
                    strength=_strength(aspect.negative, aspect.avg_confidence),
                )
            )

    # --- topic insight -----------------------------------------------------------
    if topics.adequate and topics.topics:
        biggest = topics.topics[0]
        insights.append(
            InsightOut(
                id="topic-dominant",
                kind="topic",
                title=f"Dominant topic: {', '.join(biggest.keywords[:4])}",
                statement=(
                    f"{biggest.size} of {sum(t.size for t in topics.topics)} clustered reviews talk about "
                    f"{', '.join(biggest.keywords[:6])}"
                    + (f" — mostly {biggest.sentiment} sentiment." if biggest.sentiment else ".")
                ),
                evidence=InsightEvidence(
                    statistic=f"topic size {biggest.size}",
                    review_ids=[r["review_id"] for r in biggest.representative[:3]],
                ),
                strength="moderate",
            )
        )

    _ = math  # kept for future Wilson-interval strength scoring
    return InsightsOut(
        dataset_id=dataset.id,
        generated_from=["analytics", "aspects", "topics"],
        insights=insights,
    )
