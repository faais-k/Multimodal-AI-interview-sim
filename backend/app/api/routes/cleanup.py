"""
Session storage cleanup endpoint.

Deletes session directories that are:
  - Older than max_age_hours (default 48h), AND
  - Either completed (final_decision.json exists) OR abandoned (no interview_state.json)

Never deletes in-progress sessions (interview_state.json exists but no final_decision.json).

Authentication: if env var CLEANUP_SECRET is set, callers must supply it via
the X-Cleanup-Secret header. The lifespan auto-call in main.py bypasses HTTP
headers and is not affected by this check.
"""

import os
import shutil
from datetime import datetime, timedelta

from fastapi import APIRouter, Header, HTTPException
from backend.app.core.storage import get_storage_dir

router = APIRouter()

MAX_SESSION_AGE_HOURS = 48

# BUG 6 fix: secret key auth for the HTTP endpoint
CLEANUP_SECRET = os.getenv("CLEANUP_SECRET", "")


@router.post("/admin/cleanup")
async def cleanup_old_sessions(
    max_age_hours: int = MAX_SESSION_AGE_HOURS,
    x_cleanup_secret: str = Header(default=""),
    enforce_auth: bool = True,
):
    """Delete old completed or abandoned sessions.

    Requires X-Cleanup-Secret header if CLEANUP_SECRET env var is set.
    The startup lifespan call in main.py calls this as a Python function
    and bypasses the header check intentionally.
    """
    # BUG 6: Reject unauthorised callers when a secret is configured
    if enforce_auth and not CLEANUP_SECRET:
        raise HTTPException(
            status_code=503,
            detail="Cleanup endpoint is disabled until CLEANUP_SECRET is configured.",
        )

    if enforce_auth and x_cleanup_secret != CLEANUP_SECRET:
        raise HTTPException(status_code=403, detail="Invalid cleanup secret.")

    storage = get_storage_dir()
    if not storage.exists():
        return {"deleted": 0, "skipped": 0, "cutoff": None}

    cutoff  = datetime.utcnow() - timedelta(hours=max_age_hours)
    deleted = 0
    skipped = 0

    for session_dir in storage.iterdir():
        if not session_dir.is_dir():
            continue

        # Check directory age via mtime
        mtime = datetime.utcfromtimestamp(session_dir.stat().st_mtime)
        if mtime > cutoff:
            skipped += 1
            continue

        state_path    = session_dir / "interview_state.json"
        decision_path = session_dir / "final_decision.json"

        # Safe to delete:
        #   - completed interview: final_decision.json exists
        #   - abandoned before interview started: no interview_state.json
        if decision_path.exists() or not state_path.exists():
            shutil.rmtree(session_dir, ignore_errors=True)
            deleted += 1
        else:
            # In-progress session — leave it alone
            skipped += 1

    return {
        "deleted": deleted,
        "skipped": skipped,
        "cutoff":  cutoff.isoformat(),
    }
