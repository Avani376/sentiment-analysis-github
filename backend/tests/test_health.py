"""Health and operational endpoints."""


def test_health_ok(client):
    response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["database"] == "ok"
    assert body["registered_models"] >= 2
    assert body["app"] == "SENTINEX AI"


def test_openapi_document_available(client):
    response = client.get("/openapi.json")
    assert response.status_code == 200
    paths = response.json()["paths"]
    assert "/api/v1/analyze/single" in paths
    assert "/api/v1/analyze/batch" in paths
    assert "/api/v1/datasets/upload" in paths
    assert "/api/v1/models" in paths
    assert "/api/v1/models/compare" in paths
