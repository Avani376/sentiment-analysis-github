"""Aspect-based sentiment analysis — transparent rule-based baseline.

HONEST SCOPE (stated in the API response itself): this is a lexicon +
clause-polarity baseline, NOT a trained ABSA model. Aspect terms come from a
curated lexicon mapped to categories; polarity comes from running a registered
sentiment model on the clause that contains the term; the exact clause is
returned as evidence so every claim is checkable. A trained SemEval-2014
Task 4 model is the documented next step.
"""

from __future__ import annotations

import re

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.entities import Dataset, Review
from app.schemas.insights import AspectAggregate, AspectMention, AspectsOut

#: curated lexicon: surface term -> aspect category
ASPECT_LEXICON: dict[str, str] = {
    # battery & charging
    "battery life": "battery", "battery": "battery", "charge": "battery",
    "charging": "battery", "charger": "battery",
    # pricing
    "price": "pricing", "pricing": "pricing", "cost": "pricing",
    "expensive": "pricing", "cheap": "pricing", "value": "pricing", "worth": "pricing",
    # delivery & shipping
    "delivery": "delivery", "shipping": "delivery", "arrived": "delivery",
    "package": "delivery", "courier": "delivery",
    # support
    "customer support": "support", "support": "support", "customer service": "support",
    "warranty": "support", "refund": "support",
    # performance
    "performance": "performance", "speed": "performance", "lag": "performance",
    "crash": "performance", "crashes": "performance", "freeze": "performance", "slow": "performance",
    # quality
    "quality": "quality", "build": "quality", "sturdy": "quality", "flimsy": "quality",
    "durable": "quality", "broke": "quality", "broken": "quality",
    # design
    "design": "design", "look": "design", "looks": "design", "beautiful": "design",
    "sleek": "design", "weight": "design",
    # usability
    "easy to use": "usability", "intuitive": "usability", "confusing": "usability",
    "setup": "usability", "interface": "usability",
    # app / software
    "app": "app", "application": "app", "software": "app", "update": "app",
    # hardware specifics
    "camera": "camera", "photo": "camera", "photos": "camera", "video": "camera",
    "screen": "screen", "display": "screen",
    "sound": "sound", "audio": "sound", "speaker": "sound", "bass": "sound", "microphone": "sound",
}

_CLAUSE_SPLIT = re.compile(
    r"(?<=[.!?])\s+|,\s+|\s+but\s+|\s+however\s+|\s+though\s+|\s+although\s+|\s+while\s+",
    re.IGNORECASE,
)
_MIN_CLAUSE_WORDS = 3

METHOD = (
    "Rule-based baseline: curated aspect lexicon + clause-level polarity from "
    "tfidf_logreg_imdb_v1. Every claim carries its exact evidence clause. "
    "Not a trained ABSA model (SemEval-2014 Task 4 is the documented next step)."
)


def _split_clauses(text: str) -> list[str]:
    clauses = [c.strip() for c in _CLAUSE_SPLIT.split(text) if c.strip()]
    return [c for c in clauses if len(c.split()) >= _MIN_CLAUSE_WORDS]


def _match_category(clause: str) -> tuple[str, str] | None:
    lowered = clause.lower()
    # longest term wins (e.g. "battery life" before "battery")
    best: tuple[str, str] | None = None
    for term, category in ASPECT_LEXICON.items():
        if re.search(rf"\b{re.escape(term)}\b", lowered):
            if best is None or len(term) > len(best[0]):
                best = (term, category)
    return best


def dataset_aspects(db: Session, dataset: Dataset) -> AspectsOut:
    from app.services.registry import get_registry

    model = get_registry().get("tfidf_logreg_imdb_v1")
    model._ensure_loaded()

    reviews = db.scalars(
        select(Review).where(Review.dataset_id == dataset.id).order_by(Review.id)
    ).all()

    mentions: list[AspectMention] = []
    clauses_analyzed = 0
    for review in reviews:
        for clause in _split_clauses(review.text):
            clauses_analyzed += 1
            match = _match_category(clause)
            if match is None:
                continue
            term, category = match
            result = model.predict_single(clause)
            mentions.append(
                AspectMention(
                    category=category,
                    term=term,
                    polarity=result.label,
                    confidence=result.confidence,
                    evidence=clause,
                    review_id=review.id,
                )
            )

    grouped: dict[str, list[AspectMention]] = {}
    for mention in mentions:
        grouped.setdefault(mention.category, []).append(mention)

    aggregates = []
    for category, items in sorted(grouped.items(), key=lambda kv: -len(kv[1])):
        confidences = [m.confidence for m in items]
        positives = sorted(
            (m for m in items if m.polarity == "positive"), key=lambda m: -m.confidence
        )
        negatives = sorted(
            (m for m in items if m.polarity == "negative"), key=lambda m: -m.confidence
        )
        aggregates.append(
            AspectAggregate(
                category=category,
                mentions=len(items),
                positive=len(positives),
                negative=len(negatives),
                neutral=len(items) - len(positives) - len(negatives),
                avg_confidence=round(sum(confidences) / len(confidences), 4),
                positive_evidence=positives[:2],
                negative_evidence=negatives[:2],
            )
        )

    return AspectsOut(
        dataset_id=dataset.id,
        method=METHOD,
        clauses_analyzed=clauses_analyzed,
        aspects=aggregates,
    )
