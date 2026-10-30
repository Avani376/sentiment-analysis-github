"""API integration tests for /api/v1/datasets/*."""

from __future__ import annotations

SAMPLE_CSV = (
    "review_id,text,sentiment,posted_at\n"
    '1,"Loved it, amazing quality and fast delivery",positive,2024-01-05\n'
    '2,"Broke after two days, support never replied",negative,2024-01-06\n'
    '3,"Great value for the price",Positive,2024-01-07\n'
    '4,"Loved it, amazing quality and fast delivery",positive,2024-01-08\n'  # duplicate text
    '5,"",negative,2024-01-09\n'  # missing text
    '6,"It works okay I guess",meh,2024-01-10\n'  # invalid label
)


def test_upload_with_explicit_mapping(client, csv_file):
    files = csv_file(SAMPLE_CSV, extra_fields={"text_column": "text", "label_column": "sentiment"})
    response = client.post("/api/v1/datasets/upload", files=files)
    assert response.status_code == 201, response.text
    body = response.json()

    stats = body["stats"]
    assert stats["row_count"] == 6
    assert stats["missing_text_rows"] == 1
    assert stats["duplicate_rows"] == 1
    assert stats["invalid_label_rows"] == 1
    assert stats["valid_rows"] == 4  # invalid-label row is kept with label=None

    assert body["text_column"] == "text"
    assert body["label_column"] == "sentiment"
    assert len(body["preview"]) == 4
    # Labels are normalized; the raw value is preserved for traceability and
    # rows with unmappable labels are kept with label=None (never silently dropped).
    assert all(r["label"] in {"positive", "negative", None} for r in body["preview"])
    row_6 = next(r for r in body["preview"] if r["raw_label"] == "meh")
    assert row_6["label"] is None

    return body["id"]


def test_upload_auto_detects_columns(client, csv_file):
    files = csv_file(SAMPLE_CSV)
    response = client.post("/api/v1/datasets/upload", files=files)
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["text_column"] == "text"
    assert body["label_column"] == "sentiment"
    assert body["id_column"] == "review_id"
    assert body["timestamp_column"] == "posted_at"


def test_reviews_pagination_search_and_filters(client, csv_file):
    dataset_id = None
    files = csv_file(SAMPLE_CSV, extra_fields={"text_column": "text", "label_column": "sentiment"})
    dataset_id = client.post("/api/v1/datasets/upload", files=files).json()["id"]

    page = client.get(f"/api/v1/datasets/{dataset_id}/reviews", params={"page_size": 2})
    assert page.status_code == 200
    body = page.json()
    assert body["total"] == 4
    assert body["pages"] == 2
    assert len(body["items"]) == 2

    positives = client.get(
        f"/api/v1/datasets/{dataset_id}/reviews", params={"label": "positive"}
    ).json()
    assert positives["total"] == 2

    search = client.get(
        f"/api/v1/datasets/{dataset_id}/reviews", params={"q": "delivery"}
    ).json()
    assert search["total"] == 1
    assert "delivery" in search["items"][0]["text"]


def test_upload_unknown_mapped_column_returns_422(client, csv_file):
    files = csv_file(SAMPLE_CSV, extra_fields={"text_column": "nope"})
    response = client.post("/api/v1/datasets/upload", files=files)
    assert response.status_code == 422
    error = response.json()["error"]
    assert error["code"] == "unknown_columns"
    assert "nope" in error["details"]["missing"]


def test_upload_rejects_non_csv_extension(client, csv_file):
    files = csv_file(SAMPLE_CSV, filename="data.txt")
    response = client.post("/api/v1/datasets/upload", files=files)
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "unsupported_file_type"


def test_upload_rejects_oversized_file(client, csv_file):
    big_row = 'x,"' + "a" * 200 + '",positive,2024-01-01\n'
    content = "id,text,label,ts\n" + big_row * 6000  # > 1 MB (test limit)
    files = csv_file(content, extra_fields={"text_column": "text"})
    response = client.post("/api/v1/datasets/upload", files=files)
    assert response.status_code == 413
    assert response.json()["error"]["code"] == "upload_too_large"


def test_upload_empty_file_rejected(client, csv_file):
    response = client.post("/api/v1/datasets/upload", files=csv_file(""))
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "empty_upload"


def test_list_datasets_and_delete(client, csv_file):
    files = csv_file(SAMPLE_CSV, extra_fields={"text_column": "text", "label_column": "sentiment"})
    dataset_id = client.post("/api/v1/datasets/upload", files=files).json()["id"]

    listing = client.get("/api/v1/datasets")
    assert listing.status_code == 200
    assert any(d["id"] == dataset_id for d in listing.json())

    deleted = client.delete(f"/api/v1/datasets/{dataset_id}")
    assert deleted.status_code == 204

    assert client.get(f"/api/v1/datasets/{dataset_id}").status_code == 404
    assert client.get(f"/api/v1/datasets/{dataset_id}/reviews").status_code == 404
    assert client.delete(f"/api/v1/datasets/{dataset_id}").status_code == 404


def test_dataset_not_found_envelope(client):
    response = client.get("/api/v1/datasets/does-not-exist")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "dataset_not_found"
