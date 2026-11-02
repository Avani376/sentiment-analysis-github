"""Topic discovery — TF-IDF + KMeans baseline (seeded, on demand, honest).

Deliberately simple and CPU-only: works on small datasets, needs no model
download. BERTopic + sentence embeddings is the documented upgrade path.
Outliers are respected: we never force every review into a "meaningful" topic
and small datasets get an explicit `adequate: false` response.
"""

from __future__ import annotations

from collections import Counter

from sklearn.cluster import KMeans
from sklearn.feature_extraction.text import TfidfVectorizer
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.entities import Dataset, Prediction, Review
from app.schemas.insights import TopicOut, TopicsOut

METHOD = "TF-IDF (unigrams+bigrams, min_df=2) + KMeans (seed 42, n_init=10)"


def dataset_topics(db: Session, dataset: Dataset, k: int | None = None) -> TopicsOut:
    rows = db.scalars(
        select(Review).where(Review.dataset_id == dataset.id).order_by(Review.id)
    ).all()
    n = len(rows)
    if n < 8:
        return TopicsOut(
            dataset_id=dataset.id,
            method=METHOD,
            adequate=False,
            message=f"Only {n} review(s) — topic clustering needs at least 8 for meaningful groups.",
            topics=[],
        )

    texts = [r.text for r in rows]
    vectorizer = TfidfVectorizer(
        max_features=400, stop_words="english", min_df=2, ngram_range=(1, 2)
    )
    matrix = vectorizer.fit_transform(texts)
    if matrix.shape[1] < 4:
        return TopicsOut(
            dataset_id=dataset.id,
            method=METHOD,
            adequate=False,
            message="Not enough distinctive vocabulary in this dataset for clustering.",
            topics=[],
        )

    chosen_k = k if k is not None else max(2, min(6, n // 10))
    chosen_k = max(2, min(chosen_k, n - 1))
    model = KMeans(n_clusters=chosen_k, random_state=42, n_init=10).fit(matrix)
    terms = vectorizer.get_feature_names_out()

    # persisted sentiment (first model with predictions) for topic-level polarity
    sentiment_by_review: dict[int, str] = {}
    first_model = db.scalars(
        select(Prediction.model_key).where(
            Prediction.review_id.in_([r.id for r in rows])
        )
    ).first()
    if first_model:
        for review_id, label in db.execute(
            select(Prediction.review_id, Prediction.label).where(
                Prediction.model_key == first_model,
                Prediction.review_id.in_([r.id for r in rows]),
            )
        ).all():
            sentiment_by_review[review_id] = label

    topics: list[TopicOut] = []
    for cluster_id in range(chosen_k):
        member_indices = [i for i, label in enumerate(model.labels_) if label == cluster_id]
        if not member_indices:
            continue
        centroid = model.cluster_centers_[cluster_id]
        top_term_indices = centroid.argsort()[::-1][:8]
        keywords = [terms[i] for i in top_term_indices if centroid[i] > 0]

        # representatives: closest member to the centroid
        import numpy as np

        distances = np.linalg.norm(
            matrix[member_indices] - centroid, axis=1
        )
        order = distances.argsort()
        representative = [
            {"review_id": rows[member_indices[i]].id, "text": rows[member_indices[i]].text[:280]}
            for i in order[:3]
        ]

        labels = [sentiment_by_review.get(rows[i].id) for i in member_indices]
        counted = Counter(lbl for lbl in labels if lbl)
        positive = counted.get("positive", 0)
        negative = counted.get("negative", 0)
        sentiment = None
        if positive + negative:
            sentiment = "positive" if positive >= negative else "negative"

        topics.append(
            TopicOut(
                topic_id=cluster_id,
                size=len(member_indices),
                keywords=keywords,
                sentiment=sentiment,
                positive=positive,
                negative=negative,
                representative=representative,
            )
        )

    topics.sort(key=lambda t: -t.size)
    return TopicsOut(dataset_id=dataset.id, method=METHOD, adequate=True, topics=topics)
