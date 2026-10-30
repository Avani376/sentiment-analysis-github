"""Unit tests: label normalization, adapters, and registry behaviour."""

from __future__ import annotations

import pytest

from app.core.config import get_settings
from app.core.errors import NotFoundError
from app.services.registry import (
    LABEL_NEGATIVE,
    LABEL_POSITIVE,
    normalize_label,
)


def test_normalize_label_aliases():
    assert normalize_label("1") == LABEL_POSITIVE
    assert normalize_label("POSITIVE") == LABEL_POSITIVE
    assert normalize_label("pos") == LABEL_POSITIVE
    assert normalize_label(0) == LABEL_NEGATIVE
    assert normalize_label("NEG") == LABEL_NEGATIVE
    assert normalize_label("2") == "neutral"
    with pytest.raises(ValueError):
        normalize_label("meh")


def test_legacy_model_loads_from_committed_artifact():
    from app.services.registry import build_registry

    registry = build_registry(get_settings())
    model = registry.get("tfidf_logreg_legacy")
    assert model.is_cached() is True
    model._ensure_loaded()

    result = model.predict_single("This movie was wonderful, brilliant acting and a great story.")
    assert result.label == LABEL_POSITIVE
    assert result.confidence > 0.5
    assert set(result.probabilities) == {LABEL_POSITIVE, LABEL_NEGATIVE}
    assert abs(sum(result.probabilities.values()) - 1.0) < 1e-6

    negative = model.predict_single("Awful plot, terrible acting, a complete waste of time.")
    assert negative.label == LABEL_NEGATIVE
    assert negative.confidence > 0.5


def test_registry_unknown_key_raises_not_found():
    from app.services.registry import build_registry

    registry = build_registry(get_settings())
    with pytest.raises(NotFoundError):
        registry.get("does_not_exist")


def test_binary_models_never_emit_neutral():
    from app.services.registry import build_registry

    registry = build_registry(get_settings())
    for key in ("tfidf_logreg_legacy", "tfidf_logreg_imdb_v1"):
        model = registry.get(key)
        assert model.metadata.supports_neutral is False
        assert "neutral" not in model.metadata.labels


def test_imdb_v1_available_when_artifact_committed():
    """The retrained artifact is committed with the repository; if a checkout
    predates it, this test is skipped rather than silently degraded."""

    from app.services.registry import build_registry

    settings = get_settings()
    if not settings.imdb_model_path.is_file():
        pytest.skip("tfidf_logreg_imdb_v1 artifact not present in this checkout")
    registry = build_registry(settings)
    model = registry.get("tfidf_logreg_imdb_v1")
    assert model.is_cached() is True
    model._ensure_loaded()
    result = model.predict_single("A masterpiece of cinema with outstanding performances.")
    assert result.label == LABEL_POSITIVE
