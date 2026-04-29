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
from backend.app.models.session import SessionStatus

# Configure module-level logger
logger = logging.getLogger(__name__)

# Legal state machine transitions to enforce consistency
ALLOWED_TRANSITIONS = {
    SessionStatus.CREATED: [SessionStatus.PREFLIGHT_COMPLETE, SessionStatus.FAILED],
    SessionStatus.PREFLIGHT_COMPLETE: [SessionStatus.QUESTION_ACTIVE, SessionStatus.FAILED],
    SessionStatus.QUESTION_ACTIVE: [
        SessionStatus.QUESTION_ACTIVE,    # Idempotent re-calls
        SessionStatus.ANSWER_PENDING,    # Audio answer start
        SessionStatus.SCORING_PENDING,   # Text answer start
        SessionStatus.INTERVIEW_COMPLETE,# Skip/Completion
        SessionStatus.REPORT_GENERATED,  # Direct completion
        SessionStatus.FAILED
    ],
    SessionStatus.ANSWER_PENDING: [
        SessionStatus.SCORING_PENDING, 
        SessionStatus.QUESTION_ACTIVE,   # Fallback/Recovery
        SessionStatus.FAILED, 
        SessionStatus.TIMED_OUT
    ],
    SessionStatus.SCORING_PENDING: [
        SessionStatus.QUESTION_ACTIVE, 
        SessionStatus.FOLLOWUP_PENDING, 
        SessionStatus.INTERVIEW_COMPLETE, 
        SessionStatus.FAILED, 
        SessionStatus.TIMED_OUT
    ],
    SessionStatus.FOLLOWUP_PENDING: [SessionStatus.QUESTION_ACTIVE, SessionStatus.FAILED],
    SessionStatus.INTERVIEW_COMPLETE: [
        SessionStatus.INTERVIEW_COMPLETE, # Idempotent
        SessionStatus.REPORT_GENERATED, 
        SessionStatus.FAILED
    ],
    SessionStatus.REPORT_GENERATED: [SessionStatus.REPORT_GENERATED],  # Terminal idempotent
    SessionStatus.FAILED: [
        SessionStatus.CREATED, 
        SessionStatus.QUESTION_ACTIVE, 
        SessionStatus.ANSWER_PENDING, 
        SessionStatus.SCORING_PENDING,
        SessionStatus.FAILED
    ],
    SessionStatus.TIMED_OUT: [SessionStatus.SCORING_PENDING, SessionStatus.QUESTION_ACTIVE, SessionStatus.TIMED_OUT],
}


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
    from backend.app.core.metrics import record_interview_event

    record_interview_event("started")

    if not db_available():
        return
    try:
        db = get_db()
        await db.sessions.insert_one(
            {
                "session_id": session_id,
                "user_id": user_id,
                "candidate_name": candidate_name,
                "job_role": job_role,
                "expertise_level": expertise_level,
                "status": SessionStatus.CREATED,
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow(),
            }
        )
    except Exception as e:
        _log_db_error("create_session_record", session_id, e)


async def update_session_status(
    session_id: str,
    status: SessionStatus,
    extra: Dict[str, Any] = None,
    force: bool = False,
) -> None:
    """Update session status with transition validation and heartbeats."""
    from backend.app.core.metrics import record_interview_event

    if not db_available():
        return

    try:
        db = get_db()
        current_session = await db.sessions.find_one({"session_id": session_id})
        old_status = current_session.get("status") if current_session else None

        # 1. Transition Validation (unless forced or new session)
        if old_status and not force:
            old_status_enum = SessionStatus(old_status)
            
            # Allow idempotency (self-transition) without warning
            if status == old_status_enum:
                return

            allowed = ALLOWED_TRANSITIONS.get(old_status_enum, [])
            if status not in allowed:
                logger.warning(
                    f"⚠️ Illegal transition attempt for {session_id}: {old_status} -> {status}"
                )
                # In production, we might raise an error here. For now, we log and allow if it's FAILED.
                if status != SessionStatus.FAILED:
                    return

        # 2. Heartbeats & Timestamps
        now = datetime.utcnow()
        update = {
            "status": status,
            "updated_at": now,
            "last_activity_at": now,
        }

        # Track when we start heavy work (ASR/LLM)
        if status in [SessionStatus.ANSWER_PENDING, SessionStatus.SCORING_PENDING]:
            update["processing_started_at"] = now

        if status == SessionStatus.INTERVIEW_COMPLETE:
            record_interview_event("completed")
        elif status == SessionStatus.REPORT_GENERATED:
            record_interview_event("reported")

        if extra:
            update.update(extra)

        await db.sessions.update_one(
            {"session_id": session_id},
            {"$set": update},
            upsert=True,
        )
    except Exception as e:
        _log_db_error("update_session_status", session_id, e)


async def get_session_status_db(session_id: str) -> Optional[Dict[str, Any]]:
    """Retrieve the current session document (status, timestamps, extra)."""
    if not db_available():
        return None
    try:
        db = get_db()
        doc = await db.sessions.find_one({"session_id": session_id}, {"_id": 0})
        return doc
    except Exception as e:
        _log_db_error("get_session_status_db", session_id, e)
        return None


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
            {
                "$set": {
                    "session_id": session_id,
                    "user_id": user_id,
                    "report": report,
                    "analytics": analytics or {},
                    "saved_at": datetime.utcnow(),
                }
            },
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
        await db.violations.insert_one(
            {
                "session_id": session_id,
                "user_id": user_id,
                "event": violation,
                "logged_at": datetime.utcnow(),
            }
        )
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
        cursor = db.violations.find({"session_id": session_id}, {"_id": 0}).sort("logged_at", 1)
        return await cursor.to_list(length=500)
    except Exception as e:
        _log_db_error("get_session_violations", session_id, e)
        return []
