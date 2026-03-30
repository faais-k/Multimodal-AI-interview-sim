"""
Admin endpoints for session management (MongoDB-backed).

These endpoints are read-only and only return data when MongoDB is connected.
They fall back gracefully to empty results in flat-file mode.
"""

import os
from fastapi import APIRouter, Header, HTTPException

from backend.app.core.db_ops import list_sessions, get_session_report, get_session_violations
from backend.app.core.database import db_available

router = APIRouter(tags=["Admin"])

# Optional admin secret — same pattern as cleanup endpoint
ADMIN_SECRET = os.getenv("ADMIN_SECRET", "")


def _check_auth(x_admin_secret: str) -> None:
    if ADMIN_SECRET and x_admin_secret != ADMIN_SECRET:
        raise HTTPException(status_code=403, detail="Invalid admin secret.")


@router.get("/admin/sessions")
async def get_sessions(
    limit: int = 50,
    x_admin_secret: str = Header(default=""),
):
    """List recent sessions (newest first). Requires MongoDB."""
    _check_auth(x_admin_secret)
    sessions = await list_sessions(limit)
    return {
        "sessions":      sessions,
        "count":         len(sessions),
        "mongodb_mode":  db_available(),
    }


@router.get("/admin/sessions/{session_id}/report")
async def get_session_report_endpoint(
    session_id: str,
    x_admin_secret: str = Header(default=""),
):
    """Get a session's final report from MongoDB."""
    _check_auth(x_admin_secret)
    report = await get_session_report(session_id)
    if not report:
        raise HTTPException(status_code=404, detail="Report not found in MongoDB.")
    return report


@router.get("/admin/sessions/{session_id}/violations")
async def get_violations_endpoint(
    session_id: str,
    x_admin_secret: str = Header(default=""),
):
    """Get all violations for a session from MongoDB."""
    _check_auth(x_admin_secret)
    violations = await get_session_violations(session_id)
    return {"violations": violations, "count": len(violations)}
