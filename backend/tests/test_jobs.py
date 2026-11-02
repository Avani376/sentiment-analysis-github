"""Integration tests: background dataset analysis, analytics, CSV export."""

from __future__ import annotations

import time

SAMPLE = (
    "review_id,text,sentiment,posted_at\n"
    '1,"Absolutely wonderful quality and fast delivery",positive,2024-01-01\n'
    '2,"Broke immediately and support ignored every email",negative,2024-01-02\n'
    '3,"Works as expected, nothing more",neutral,2024-01-03\n'
)


def _upload(client, csv_file) -> str:
    files = csv_file(SAMPLE, extra_fields={"text_column": "text", "label_column": "sentiment"})
    response = client.post("/api/v1/datasets/upload", files=files)
    assert response.status_code == 201, response.text
    return response.json()["id"]


def _wait_for_job(client, job_id: str, timeout_s: float = 90.0) -> dict:
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        body = client.get(f"/api/v1/jobs/{job_id}").json()
        if body["status"] in ("succeeded", "failed"):
            return body
        time.sleep(0.5)
    raise TimeoutError(f"job {job_id} did not finish in {timeout_s}s")


def test_full_bulk_analysis_pipeline(client, csv_file):
    dataset_id = _upload(client, csv_file)

    # unknown model key is rejected at queue time
    bad = client.post(
        f"/api/v1/datasets/{dataset_id}/analyze", json={"models": ["does_not_exist"]}
    )
    assert bad.status_code == 404

    launched = client.post(f"/api/v1/datasets/{dataset_id}/analyze")
    assert launched.status_code == 202, launched.text
    job = launched.json()
    assert job["status"] in ("queued", "running")

    finished = _wait_for_job(client, job["id"])
    assert finished["status"] == "succeeded", finished.get("error_message")
    # 3 reviews x 2 available TF-IDF models = 6 prediction passes
    assert finished["progress_current"] == finished["progress_total"] == 6

    # analytics reflect persisted predictions for every model x review
    analytics = client.get(f"/api/v1/datasets/{dataset_id}/analytics").json()
    assert analytics["has_results"] is True
    assert analytics["total_predictions"] == 6
    assert len(analytics["per_model"]) == 2
    for model in analytics["per_model"]:
        assert sum(model["label_counts"].values()) == 3
        assert model["avg_confidence"] is not None
    assert analytics["agreement"], "paired models must produce an agreement figure"
    assert analytics["examples"]["positive"], "confident positive examples expected"

    # export CSV contains one row per review and per-model prediction columns
    export = client.get(f"/api/v1/datasets/{dataset_id}/export")
    assert export.status_code == 200
    assert export.headers["content-type"].startswith("text/csv")
    lines = export.text.strip().splitlines()
    assert len(lines) == 4  # header + 3 reviews
    header = lines[0].split(",")
    assert "tfidf_logreg_legacy_label" in header
    assert "tfidf_logreg_imdb_v1_confidence" in header


def test_upload_with_zero_valid_rows_is_rejected(client, csv_file):
    """A CSV whose rows all fail cleaning never becomes a dataset — the 422
    surfaces at upload time, so an empty dataset can never reach /analyze."""
    empty = 'text,label\n"",positive\n'
    files = csv_file(empty, extra_fields={"text_column": "text", "label_column": "label"})
    response = client.post("/api/v1/datasets/upload", files=files)
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "no_valid_rows"


def test_job_poll_unknown_id(client):
    assert client.get("/api/v1/jobs/does-not-exist").status_code == 404
