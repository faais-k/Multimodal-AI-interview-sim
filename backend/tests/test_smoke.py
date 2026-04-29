import pytest

def test_health_check(client):
    """Verify health endpoint works."""
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"

def test_root_endpoint(client):
    """Verify root endpoint works."""
    response = client.get("/")
    assert response.status_code == 200
    assert "Ascent" in response.json()["message"]

def test_create_session(client):
    """Verify we can create a session."""
    response = client.post("/api/session/create")
    assert response.status_code == 200
    data = response.json()
    assert "session_id" in data
