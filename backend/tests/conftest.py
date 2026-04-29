import pytest
from fastapi.testclient import TestClient
from backend.app.main import app

@pytest.fixture
def client():
    """Returns a FastAPI TestClient."""
    return TestClient(app)

@pytest.fixture
def mock_session_id():
    """Returns a dummy session ID."""
    return "test-session-123"
