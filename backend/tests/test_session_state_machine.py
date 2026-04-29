"""
Tests for the Session State Machine.

Validates the SessionStatus enum and that the db_ops layer
uses it correctly. All MongoDB calls are mocked so no real
database connection is needed.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch


# ── SessionStatus Enum ────────────────────────────────────────────────────────

def test_session_status_values_are_strings():
    """SessionStatus values are strings so MongoDB stores human-readable text."""
    from backend.app.models.session import SessionStatus
    for status in SessionStatus:
        assert isinstance(status.value, str)
        assert len(status.value) > 0


def test_session_status_complete_lifecycle_order():
    """All expected lifecycle statuses exist in the enum."""
    from backend.app.models.session import SessionStatus
    required = {
        "created",
        "preflight_complete",
        "question_active",
        "answer_pending",
        "scoring_pending",
        "interview_complete",
        "report_generated",
    }
    actual = {s.value for s in SessionStatus}
    assert required.issubset(actual), f"Missing statuses: {required - actual}"


# ── db_ops state transitions ──────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_create_session_record_uses_created_status():
    """create_session_record inserts with SessionStatus.CREATED."""
    from backend.app.models.session import SessionStatus

    mock_collection = AsyncMock()
    mock_db = MagicMock()
    mock_db.sessions = mock_collection

    with patch("backend.app.core.db_ops.db_available", return_value=True), \
         patch("backend.app.core.db_ops.get_db", return_value=mock_db):
        from backend.app.core.db_ops import create_session_record
        await create_session_record("test-session-001", user_id="user-1")

    mock_collection.insert_one.assert_called_once()
    call_args = mock_collection.insert_one.call_args[0][0]
    assert call_args["status"] == SessionStatus.CREATED
    assert call_args["session_id"] == "test-session-001"
    assert call_args["user_id"] == "user-1"


@pytest.mark.asyncio
async def test_update_session_status_accepts_enum():
    """update_session_status accepts a SessionStatus enum and writes it."""
    from backend.app.models.session import SessionStatus

    mock_collection = AsyncMock()
    mock_db = MagicMock()
    mock_db.sessions = mock_collection

    with patch("backend.app.core.db_ops.db_available", return_value=True), \
         patch("backend.app.core.db_ops.get_db", return_value=mock_db):
        from backend.app.core.db_ops import update_session_status
        await update_session_status("test-session-001", SessionStatus.QUESTION_ACTIVE)

    mock_collection.update_one.assert_called_once()
    update_doc = mock_collection.update_one.call_args[0][1]["$set"]
    assert update_doc["status"] == SessionStatus.QUESTION_ACTIVE


@pytest.mark.asyncio
async def test_db_ops_noop_when_db_unavailable():
    """db_ops silently skip when MongoDB is not connected."""
    with patch("backend.app.core.db_ops.db_available", return_value=False):
        from backend.app.core.db_ops import create_session_record, update_session_status
        from backend.app.models.session import SessionStatus
        # Should not raise
        await create_session_record("session-xyz")
        await update_session_status("session-xyz", SessionStatus.SCORING_PENDING)


# ── State machine progression logic ──────────────────────────────────────────

def test_status_enum_string_equality():
    """SessionStatus values compare equal to their string representation."""
    from backend.app.models.session import SessionStatus
    # str enum ensures value works in MongoDB filters and JSON responses
    assert SessionStatus.CREATED == "created"
    assert SessionStatus.INTERVIEW_COMPLETE == "interview_complete"
    assert SessionStatus.REPORT_GENERATED == "report_generated"
