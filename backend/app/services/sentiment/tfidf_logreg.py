"""Adapter for TF-IDF + Logistic Regression pipelines (scikit-learn).

One adapter serves two registered models:

* ``tfidf_logreg_legacy`` — the repository's original committed artifact
  (``models/tfidf_logreg.pkl``). Its training pipeline and split were never
  versioned, so it is registered as a **legacy artifact** and its historical
  metrics are always labelled as such.
* ``tfidf_logreg_imdb_v1`` — retrained in-repo on the public IMDb dataset with
  a documented, seeded pipeline (see ``backend/ml/train_logreg.py``).

Both are binary classifiers: positive/negative only, never neutral.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import joblib

from app.core.config import Settings
from app.services.registry import (
    LABEL_NEGATIVE,
    LABEL_POSITIVE,
    ModelMetadata,
    SentimentModel,
    normalize_label,
)

_RELATIVE_ARTIFACT_ROOT = Path("backend") / "artifacts" / "models"


class TfidfLogregModel(SentimentModel):
    """Sklearn pipeline adapter: single ``predict_proba`` pass per batch."""

    def __init__(self, metadata: ModelMetadata, settings: Settings, artifact_path: Path) -> None:
        super().__init__(metadata, settings)
        self._artifact_path = artifact_path
        self._pipeline: Any = None

    # -- constructors -------------------------------------------------------
    @classmethod
    def legacy(cls, settings: Settings) -> TfidfLogregModel:
        return cls(
            metadata=ModelMetadata(
                key="tfidf_logreg_legacy",
                display_name="TF-IDF + LogReg (legacy)",
                family="tfidf_logreg",
                version="legacy-2024",
                labels=(LABEL_POSITIVE, LABEL_NEGATIVE),
                supports_neutral=False,
                source="models/tfidf_logreg.pkl",
                provenance="legacy_artifact",
                card_file="tfidf_logreg_legacy.yaml",
            ),
            settings=settings,
            artifact_path=settings.legacy_model_path,
        )

    @classmethod
    def imdb_v1(cls, settings: Settings) -> TfidfLogregModel:
        return cls(
            metadata=ModelMetadata(
                key="tfidf_logreg_imdb_v1",
                display_name="TF-IDF + LogReg (IMDb v1)",
                family="tfidf_logreg",
                version="1.0.0",
                labels=(LABEL_POSITIVE, LABEL_NEGATIVE),
                supports_neutral=False,
                source="backend/artifacts/models/tfidf_logreg_imdb_v1.pkl",
                provenance="trained_in_repo",
                card_file="tfidf_logreg_imdb_v1.yaml",
            ),
            settings=settings,
            artifact_path=settings.imdb_model_path,
        )

    # -- lifecycle ----------------------------------------------------------
    def is_cached(self) -> bool | None:
        return self._artifact_path.is_file()

    def _load(self) -> None:
        if not self._artifact_path.is_file():
            raise FileNotFoundError(str(self._artifact_path))
        pipeline = joblib.load(self._artifact_path)
        if not hasattr(pipeline, "predict_proba") or not hasattr(pipeline, "classes_"):
            raise TypeError(
                f"Artifact {self._artifact_path.name} is not a probabilistic classifier pipeline."
            )
        # Fail fast on unmappable classes instead of mislabelling at inference.
        for raw_class in pipeline.classes_:
            normalize_label(raw_class)
        self._pipeline = pipeline

    # -- inference ----------------------------------------------------------
    def _predict_batch(self, texts: list[str]) -> list[dict[str, float]]:
        assert self._pipeline is not None  # guaranteed by _ensure_loaded
        proba = self._pipeline.predict_proba(texts)
        normalized = [normalize_label(c) for c in self._pipeline.classes_]

        distributions: list[dict[str, float]] = []
        for row in proba:
            dist: dict[str, float] = {}
            for label, p in zip(normalized, row, strict=True):
                # If both raw classes normalize to the same label (bad artifact),
                # keep the max instead of silently double-counting.
                dist[label] = max(dist.get(label, 0.0), float(p))
            distributions.append(dist)
        return distributions
