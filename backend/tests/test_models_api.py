"""API integration tests for /api/v1/models/*."""

from __future__ import annotations

import pytest

from app.core.config import get_settings


def test_list_models(client):
    response = client.get("/api/v1/models")
    assert response.status_code == 200
    models = {m["key"]: m for m in response.json()}

    legacy = models["tfidf_logreg_legacy"]
    assert legacy["provenance"] == "legacy_artifact"
    assert legacy["cached"] is True
    assert legacy["supports_neutral"] is False
    assert legacy["card"]["limitations"]  # model card present

    # Disabled models stay listed with enabled=false (config toggle respected).
    distilbert = models["distilbert_sst2"]
    assert distilbert["enabled"] is False
    assert distilbert["provenance"] == "pretrained_checkpoint"
    assert "neutral" not in distilbert["labels"]


def test_model_detail_contains_card(client):
    response = client.get("/api/v1/models/tfidf_logreg_legacy")
    assert response.status_code == 200
    card = response.json()["card"]
    assert "never versioned" in card["training_provenance"] or "UNVERIFIED" in card["training_provenance"]


def test_unknown_model_returns_envelope_404(client):
    response = client.get("/api/v1/models/unknown_key")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "model_not_found"


def _imdb_artifact_exists() -> bool:
    return get_settings().imdb_model_path.is_file()


@pytest.mark.skipif(not _imdb_artifact_exists(), reason="retrained artifact not committed yet")
def test_compare_includes_reproduced_and_historical(client):
    response = client.get("/api/v1/models/compare")
    assert response.status_code == 200
    evaluations = response.json()["evaluations"]
    types = {e["evaluation_type"] for e in evaluations}
    assert "historical_reference" in types
    assert "reproduced" in types

    reproduced = next(e for e in evaluations if e["evaluation_type"] == "reproduced")
    assert reproduced["model_key"] == "tfidf_logreg_imdb_v1"
    assert reproduced["dataset"]["source_url"].startswith("https://")
    assert reproduced["metrics"]["accuracy"] > 0.5


def test_compare_lists_legacy_reference_as_historical(client):
    response = client.get("/api/v1/models/compare")
    assert response.status_code == 200
    historical = [
        e for e in response.json()["evaluations"] if e["evaluation_type"] == "historical_reference"
    ]
    assert historical, "legacy reference artifact must be present"
    assert all("not" in (e["notes"] or "").lower() or "unknown" in (e["notes"] or "").lower()
               for e in historical)
