"""API integration tests for /api/v1/analyze/*."""

from __future__ import annotations

POSITIVE = "Absolutely loved it — wonderful performances and a gripping story."
NEGATIVE = "Terrible film. Boring, badly acted, and a complete waste of two hours."


def test_single_analyze_default_models(client):
    response = client.post("/api/v1/analyze/single", json={"text": POSITIVE})
    assert response.status_code == 200
    body = response.json()

    # DistilBERT is disabled in the test environment; both TF-IDF models serve.
    keys = [p["model_key"] for p in body["predictions"]]
    assert "tfidf_logreg_legacy" in keys
    assert body["text_chars"] == len(POSITIVE)

    for prediction in body["predictions"]:
        assert prediction["label"] in {"positive", "negative"}
        assert set(prediction["probabilities"]) == {"positive", "negative"}
        assert 0.0 <= prediction["confidence"] <= 1.0
        assert prediction["latency_ms"] >= 0
        assert prediction["supports_neutral"] is False

    # The API reports text length, never echoes customer text back.
    assert "text" not in body


def test_single_analyze_explicit_model(client):
    response = client.post(
        "/api/v1/analyze/single",
        json={"text": POSITIVE, "models": ["tfidf_logreg_legacy"]},
    )
    assert response.status_code == 200
    assert [p["model_key"] for p in response.json()["predictions"]] == ["tfidf_logreg_legacy"]


def test_single_analyze_disabled_model_returns_503(client):
    # conftest sets SENTINEX_ENABLE_DISTILBERT=false; it stays listed but refuses.
    response = client.post(
        "/api/v1/analyze/single",
        json={"text": POSITIVE, "models": ["distilbert_sst2"]},
    )
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "model_disabled"


def test_single_analyze_unknown_model_returns_404(client):
    response = client.post(
        "/api/v1/analyze/single",
        json={"text": POSITIVE, "models": ["nope"]},
    )
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "model_not_found"


def test_single_analyze_blank_text_returns_422(client):
    response = client.post("/api/v1/analyze/single", json={"text": "   "})
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "empty_text"


def test_batch_analyze(client):
    response = client.post("/api/v1/analyze/batch", json={"texts": [POSITIVE, NEGATIVE, POSITIVE]})
    assert response.status_code == 200
    body = response.json()
    assert body["count"] == 3

    for model_key in {p["model_key"] for p in body["predictions"]}:
        indices = sorted(p["text_index"] for p in body["predictions"] if p["model_key"] == model_key)
        assert indices == [0, 1, 2]
    assert body["batch_latency_ms"] >= 0


def test_batch_analyze_over_limit_returns_422(client):
    texts = [POSITIVE] * 101  # default batch_limit is 100
    response = client.post("/api/v1/analyze/batch", json={"texts": texts})
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "batch_limit_exceeded"


def test_batch_analyze_blank_item_returns_422(client):
    response = client.post("/api/v1/analyze/batch", json={"texts": [POSITIVE, "   "]})
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "empty_text_in_batch"


def test_error_envelope_shape_on_validation_error(client):
    response = client.post("/api/v1/analyze/single", json={})
    assert response.status_code == 422
    error = response.json()["error"]
    assert error["code"] == "validation_error"
    assert error["details"]["errors"]
