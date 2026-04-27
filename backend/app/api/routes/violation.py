"""
Anti-cheat violation logging endpoint.
Frontend sends events whenever the candidate:
  - exits fullscreen
  - switches tabs (visibilitychange)
  - defocuses the window (blur)
Each violation is timestamped and stored in violations.json.
"""
import json
import asyncio
import threading
from datetime import datetime
from typing import Dict, Any
from pathlib import Path

from fastapi import APIRouter, Depends
from backend.app.core.storage import get_storage_dir
from backend.app.core.auth import get_optional_user
from backend.app.core.db_ops import log_violation_db
from backend.app.core.validation import validate_session_id

router = APIRouter()
_session_locks: dict[str, asyncio.Lock] = {}
_session_locks_mutex = threading.Lock()


def get_session_lock(session_id: str) -> asyncio.Lock:
    with _session_locks_mutex:
        if session_id not in _session_locks:
            _session_locks[session_id] = asyncio.Lock()
        return _session_locks[session_id]


def _storage_dir() -> Path:
    return get_storage_dir()


def _now() -> str:
    return datetime.utcnow().isoformat() + "Z"


@router.post("/session/violation")
async def log_violation(payload: Dict[str, Any], user: dict = Depends(get_optional_user)):
    """
    body: {
      "session_id": "...",
      "type": "TAB_SWITCH" | "FULLSCREEN_EXIT" | "WINDOW_BLUR",
      "details": "optional string",
      "timestamp": "ISO string (optional, server time used if missing)"
    }
    """
    session_id = payload.get("session_id")
    if not session_id:
        raise HTTPException(status_code=400, detail="session_id required")
    validate_session_id(session_id)

    session_dir = _storage_dir() / session_id
    if not session_dir.exists():
        raise HTTPException(status_code=404, detail="session not found")

    v_path = session_dir / "violations.json"
    async with get_session_lock(session_id):
        violations = []
        if v_path.exists():
            try:
                violations = json.loads(v_path.read_text(encoding="utf-8"))
            except Exception:
                violations = []

        entry = {
            "type":      payload.get("type", "UNKNOWN"),
            "details":   payload.get("details", ""),
            "timestamp": payload.get("timestamp") or _now(),
            "server_ts": _now(),
        }
        violations.append(entry)
        v_path.write_text(json.dumps(violations, indent=2), encoding="utf-8")
        uid = user.get("uid") if user else None
        await log_violation_db(session_id, entry, user_id=uid)

        return {
            "status":           "ok",
            "total_violations": len(violations),
        }
