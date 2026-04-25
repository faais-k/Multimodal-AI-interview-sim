"""
MongoDB CRUD operations for session lifecycle.

All functions are async and silently no-op when db_available() is False,
so the system always falls back to flat-file mode without errors.
"""

import logging
import traceback
from datetime import datetime
from typing import Any, Dict, List, Optional

from backend.app.core.database import db_available, get_db

# Configure module-level logger
logger = logging.getLogger(__name__)


def _log_db_error(operation: str, session_id: str, exception: Exception) -> None:
    """
    Centralized error logging for database operations.
    
    Logs with appropriate severity based on exception type:
    - Connection errors: ERROR (needs immediate attention)
    - Auth errors: ERROR (configuration issue)
    - Duplicate key: WARNING (business logic issue)
    - Other errors: WARNING with full traceback
    """
    error_type = type(exception).__name__
    error_msg = str(exception)
    
    # Determine severity based on error type
    if "Connection" in error_type or "Network" in error_type or "Timeout" in error_type:
        level = logging.ERROR
        msg = f"MongoDB connection error in {operation} for session {session_id}: {error_msg}"
    elif "Authentication" in error_type or "Auth" in error_type or "Credential" in error_type:
        level = logging.ERROR
        msg = f"MongoDB authentication error in {operation} for session {session_id}: {error_msg}"
    elif "DuplicateKey" in error_type:
        level = logging.WARNING
        msg = f"MongoDB duplicate key in {operation} for session {session_id}: {error_msg}"
    else:
        level = logging.WARNING
        msg = f"MongoDB error in {operation} for session {session_id}: {error_type}: {error_msg}"
    
    logger.log(level, msg)
    
    # Log full traceback for unexpected errors at DEBUG level
    if level == logging.WARNING and "DuplicateKey" not in error_type:
        logger.debug(f"Full traceback for {operation}: {traceback.format_exc()}")


async def create_session_record(
    session_id: str,
    user_id: str = None,
    candidate_name: str = "",
    job_role: str = "",
    expertise_level: str = "fresher",
) -> None:
    """Insert a new session document when a session is created."""
    if not db_available():
        return
    try:
        db = get_db()
        await db.sessions.insert_one({
            "session_id":      session_id,
            "user_id":         user_id,
            "candidate_name":  candidate_name,
            "job_role":        job_role,
            "expertise_level": expertise_level,
            "status":          "created",
            "created_at":      datetime.utcnow(),
            "updated_at":      datetime.utcnow(),
        })
    except Exception as e:
        _log_db_error("create_session_record", session_id, e)


async def update_session_status(
    session_id: str,
    status: str,
    extra: Dict[str, Any] = None,
) -> None:
    """Update session status: created → active → completed."""
    if not db_available():
        return
    try:
        db = get_db()
        update = {"status": status, "updated_at": datetime.utcnow()}
        if extra:
            update.update(extra)
        await db.sessions.update_one(
            {"session_id": session_id},
            {"$set": update},
            upsert=True,
        )
    except Exception as e:
        _log_db_error("update_session_status", session_id, e)


async def save_final_report(
    session_id: str,
    report: Dict[str, Any],
    analytics: Dict[str, Any] = None,
    user_id: str = None,
) -> None:
    """Persist the final report + analytics to MongoDB on interview completion."""
    if not db_available():
        return
    try:
        db = get_db()
        await db.reports.update_one(
            {"session_id": session_id},
            {"$set": {
                "session_id": session_id,
                "user_id":    user_id,
                "report":     report,
                "analytics":  analytics or {},
                "saved_at":   datetime.utcnow(),
            }},
            upsert=True,
        )
    except Exception as e:
        _log_db_error("save_final_report", session_id, e)


async def log_violation_db(
    session_id: str,
    violation: Dict[str, Any],
    user_id: str = None,
) -> None:
    """Append a violation event to the violations collection."""
    if not db_available():
        return
    try:
        db = get_db()
        await db.violations.insert_one({
            "session_id": session_id,
            "user_id":    user_id,
            "event":      violation,
            "logged_at":  datetime.utcnow(),
        })
    except Exception as e:
        _log_db_error("log_violation_db", session_id, e)


async def get_session_report(session_id: str) -> Optional[Dict[str, Any]]:
    """Retrieve a completed session report from MongoDB."""
    if not db_available():
        return None
    try:
        db = get_db()
        doc = await db.reports.find_one({"session_id": session_id})
        if doc:
            doc.pop("_id", None)
        return doc
    except Exception as e:
        _log_db_error("get_session_report", session_id, e)
        return None


async def list_sessions(limit: int = 50) -> List[Dict[str, Any]]:
    """List recent sessions ordered by creation time (newest first)."""
    if not db_available():
        return []
    try:
        db = get_db()
        cursor = db.sessions.find({}, {"_id": 0}).sort("created_at", -1).limit(limit)
        return await cursor.to_list(length=limit)
    except Exception as e:
        _log_db_error("list_sessions", "N/A", e)
        return []


async def get_session_violations(session_id: str) -> List[Dict[str, Any]]:
    """Retrieve all violations for a session from MongoDB."""
    if not db_available():
        return []
    try:
        db = get_db()
        cursor = db.violations.find(
            {"session_id": session_id},
            {"_id": 0}
        ).sort("logged_at", 1)
        return await cursor.to_list(length=500)
    except Exception as e:
        _log_db_error("get_session_violations", session_id, e)
        return []
