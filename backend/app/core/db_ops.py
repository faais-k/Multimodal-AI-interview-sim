"""
MongoDB CRUD operations for session lifecycle.

All functions are async and silently no-op when db_available() is False,
so the system always falls back to flat-file mode without errors.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional

from backend.app.core.database import db_available, get_db


async def create_session_record(
    session_id: str,
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
            "candidate_name":  candidate_name,
            "job_role":        job_role,
            "expertise_level": expertise_level,
            "status":          "created",
            "created_at":      datetime.utcnow(),
            "updated_at":      datetime.utcnow(),
        })
    except Exception as e:
        print(f"⚠️  MongoDB create_session_record failed: {e}")


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
        print(f"⚠️  MongoDB update_session_status failed: {e}")


async def save_final_report(
    session_id: str,
    report: Dict[str, Any],
    analytics: Dict[str, Any] = None,
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
                "report":     report,
                "analytics":  analytics or {},
                "saved_at":   datetime.utcnow(),
            }},
            upsert=True,
        )
    except Exception as e:
        print(f"⚠️  MongoDB save_final_report failed: {e}")


async def log_violation_db(
    session_id: str,
    violation: Dict[str, Any],
) -> None:
    """Append a violation event to the violations collection."""
    if not db_available():
        return
    try:
        db = get_db()
        await db.violations.insert_one({
            "session_id": session_id,
            "event":      violation,
            "logged_at":  datetime.utcnow(),
        })
    except Exception as e:
        print(f"⚠️  MongoDB log_violation_db failed: {e}")


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
        print(f"⚠️  MongoDB get_session_report failed: {e}")
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
        print(f"⚠️  MongoDB list_sessions failed: {e}")
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
        print(f"⚠️  MongoDB get_session_violations failed: {e}")
        return []
