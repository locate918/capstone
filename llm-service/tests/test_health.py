from fastapi.testclient import TestClient

from app.main import app


def test_health_endpoint_returns_ok():
    client = TestClient(app)
    response = client.get("/health")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["service"] == "llm-service"
    assert "version" in payload
    assert "git_sha" in payload


def test_version_endpoint_returns_build_metadata():
    client = TestClient(app)
    response = client.get("/version")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["service"] == "llm-service"
    assert "version" in payload
    assert "git_sha" in payload
