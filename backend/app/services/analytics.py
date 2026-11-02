"""Per-dataset analytics: aggregate persisted predictions for dashboards."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.entities import Dataset, Prediction, Review
from app.schemas.analytics import DatasetAnalytics, ModelAnalytics, ReviewExample


def dataset_analytics(db: Session, dataset: Dataset) -> DatasetAnalytics:
    total_reviews = dataset.valid_rows

    rows = db.execute(
        select(
            Prediction.model_key,
            Prediction.model_version,
            Prediction.label,
            Prediction.confidence,
            Prediction.review_id,
        ).join(Review, Prediction.review_id == Review.id)
        .where(Review.dataset_id == dataset.id)
    ).all()

    grouped: dict[str, dict] = {}
    for model_key, model_version, label, confidence, review_id in rows:
        entry = grouped.setdefault(
            model_key,
            {"version": model_version, "counts": {}, "confidences": [], "by_review": {}},
        )
        entry["counts"][label] = entry["counts"].get(label, 0) + 1
        entry["confidences"].append(confidence)
        entry["by_review"][review_id] = (label, confidence)

    per_model = [
        ModelAnalytics(
            model_key=key,
            model_version=meta["version"],
            predictions=sum(meta["counts"].values()),
            label_counts=meta["counts"],
            avg_confidence=round(sum(meta["confidences"]) / len(meta["confidences"]), 4)
            if meta["confidences"]
            else None,
        )
        for key, meta in grouped.items()
    ]
    per_model.sort(key=lambda m: m.predictions, reverse=True)

    # pairwise agreement over reviews both models scored
    agreement: dict[str, float] = {}
    keys = list(grouped)
    for i, key_a in enumerate(keys):
        for key_b in keys[i + 1 :]:
            shared = set(grouped[key_a]["by_review"]) & set(grouped[key_b]["by_review"])
            if not shared:
                continue
            same = sum(
                grouped[key_a]["by_review"][rid][0] == grouped[key_b]["by_review"][rid][0]
                for rid in shared
            )
            agreement[f"{key_a} | {key_b}"] = round(same / len(shared), 4)

    # representative examples from the model with the most predictions
    examples: dict[str, list[ReviewExample]] = {}
    if per_model:
        primary = grouped[per_model[0].model_key]["by_review"]
        example_rows = {
            rid: text
            for rid, text in db.execute(
                select(Review.id, Review.text).where(Review.dataset_id == dataset.id)
            ).all()
        }
        for label in ("positive", "negative"):
            top = sorted(
                (
                    (confidence, rid)
                    for rid, (lbl, confidence) in primary.items()
                    if lbl == label and rid in example_rows
                ),
                reverse=True,
            )[:3]
            examples[label] = [
                ReviewExample(
                    review_id=rid, text=example_rows[rid], label=label, confidence=round(conf, 4)
                )
                for conf, rid in top
            ]

    total_predictions = sum(m.predictions for m in per_model)
    return DatasetAnalytics(
        dataset_id=dataset.id,
        total_reviews=total_reviews,
        total_predictions=total_predictions,
        has_results=total_predictions > 0,
        per_model=per_model,
        agreement=agreement,
        examples=examples,
    )
