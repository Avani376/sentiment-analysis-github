"""Auth flow tests: registration, login, sessions, protected mutations."""

from __future__ import annotations

import uuid

from fastapi.testclient import TestClient


def _unique_username() -> str:
    return f"user_{uuid.uuid4().hex[:10]}"


def test_register_login_me_logout_cycle(client):
    username = _unique_username()
    password = "secret-password-1"

    registered = client.post(
        "/api/v1/auth/register", json={"username": username, "password": password}
    )
    assert registered.status_code == 201
    assert registered.json()["username"] == username

    # A fresh client performs the login and receives the session cookie.
    session_client = TestClient(client.app)
    logged = session_client.post(
        "/api/v1/auth/login", json={"username": username, "password": password}
    )
    assert logged.status_code == 200

    me = session_client.get("/api/v1/auth/me")
    assert me.status_code == 200
    assert me.json()["username"] == username

    logout = session_client.post("/api/v1/auth/logout")
    assert logout.status_code == 204
    assert session_client.get("/api/v1/auth/me").status_code == 401


def test_register_rejects_duplicate_username(client):
    username = _unique_username()
    payload = {"username": username, "password": "secret-password-1"}
    assert client.post("/api/v1/auth/register", json=payload).status_code == 201
    duplicate = client.post("/api/v1/auth/register", json=payload)
    assert duplicate.status_code == 409
    assert duplicate.json()["error"]["code"] == "username_taken"


def test_register_rejects_weak_password_and_bad_username(client):
    weak = client.post(
        "/api/v1/auth/register", json={"username": _unique_username(), "password": "short"}
    )
    assert weak.status_code == 422
    bad_name = client.post(
        "/api/v1/auth/register",
        json={"username": "bad name!", "password": "secret-password-1"},
    )
    assert bad_name.status_code == 422


def test_login_wrong_password_returns_401(client):
    username = _unique_username()
    client.post(
        "/api/v1/auth/register", json={"username": username, "password": "secret-password-1"}
    )
    response = client.post(
        "/api/v1/auth/login", json={"username": username, "password": "wrong-password-9"}
    )
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "invalid_credentials"


def test_mutations_require_login(fresh_client, csv_file):
    sample = "text,label\nGreat product,positive\n"
    response = fresh_client.post(
        "/api/v1/datasets/upload", files=csv_file(sample, extra_fields={"text_column": "text"})
    )
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "unauthorized"
    assert fresh_client.delete("/api/v1/datasets/whatever").status_code == 401
    assert fresh_client.post("/api/v1/datasets/whatever/analyze").status_code == 401


def test_reads_stay_public(fresh_client):
    assert fresh_client.get("/api/v1/models").status_code == 200
    assert fresh_client.get("/health").status_code == 200
