# api/tests/test_security.py

from fastapi.testclient import TestClient

from app.main import app


def test_teams_requires_api_key():
    unauthenticated_client = TestClient(app)
    response = unauthenticated_client.get("/api/v1/teams/")
    assert response.status_code == 401


def test_teams_rejects_wrong_api_key():
    unauthenticated_client = TestClient(app, headers={"X-API-Key": "wrong-key"})
    response = unauthenticated_client.get("/api/v1/teams/")
    assert response.status_code == 401


def test_health_does_not_require_api_key():
    unauthenticated_client = TestClient(app)
    response = unauthenticated_client.get("/health")
    assert response.status_code == 200
