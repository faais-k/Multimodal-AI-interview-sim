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


async def _cleanup_internal(max_age_hours: int = 48):
    """Called from lifespan only."""
    storage = get_storage_dir()
    if not storage.exists():
        return {"deleted": 0, "skipped": 0, "cutoff": None}

    cutoff = datetime.utcnow() - timedelta(hours=max_age_hours)
    deleted = 0
    skipped = 0

    for session_dir in storage.iterdir():
        if not session_dir.is_dir():
            continue

        # Check session activity via state file timestamps, not directory mtime
        state_file = session_dir / "interview_state.json"
        if state_file.exists():
            try:
                state_mtime = datetime.fromtimestamp(state_file.stat().st_mtime)
                if state_mtime < cutoff:
                    # Check if session has final_decision.json (completed)
                    if (session_dir / "final_decision.json").exists():
                        shutil.rmtree(session_dir)
                        deleted += 1
                    else:
                        skipped += 1
            except Exception:
                # If we can't read timestamps, skip this directory
                skipped += 1
        else:
            # No state file means inactive session, safe to delete if old enough
            try:
                dir_mtime = datetime.fromtimestamp(session_dir.stat().st_mtime)
                if dir_mtime < cutoff:
                    shutil.rmtree(session_dir)
                    deleted += 1
            except Exception:
                skipped += 1

    return {"deleted": deleted, "skipped": skipped, "cutoff": cutoff.isoformat()}


@router.post("/admin/cleanup")
async def cleanup_old_sessions(
    max_age_hours: int = MAX_SESSION_AGE_HOURS,
    x_cleanup_secret: str = Header(default=""),
    internal: bool = False,  # Allows bypassing secret check for internal lifespan calls
):
    """Delete old completed or abandoned sessions.

    Requires X-Cleanup-Secret header if CLEANUP_SECRET env var is set.
    Bypass secret check when called internally (e.g., from lifespan).
    """
    if not internal:
        if not CLEANUP_SECRET:
            raise HTTPException(503, "Cleanup endpoint disabled until CLEANUP_SECRET is set.")
        if x_cleanup_secret != CLEANUP_SECRET:
            raise HTTPException(403, "Invalid cleanup secret.")
    return await _cleanup_internal(max_age_hours)
