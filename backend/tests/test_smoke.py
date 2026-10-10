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


def test_cors_origins_resolution(monkeypatch):
    """Verify CORS origins resolution supports Vercel and custom origins."""
    from backend.app.main import get_cors_origins

    # Test explicit ALLOWED_ORIGINS
    monkeypatch.setenv("ALLOWED_ORIGINS", "https://custom.example.com, https://another.app")
    origins, regex = get_cors_origins()
    assert "https://custom.example.com" in origins
    assert "https://another.app" in origins
    assert regex is None

    # Test default fallback for HF Space -> Vercel
    monkeypatch.delenv("ALLOWED_ORIGINS", raising=False)
    origins, regex = get_cors_origins()
    assert regex == r"^https:\/\/.*\.vercel\.app$"
    assert "*" in origins

