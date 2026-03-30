from fastapi import APIRouter, HTTPException
from pathlib import Path
import json
from typing import Any, Dict

from backend.app.core.validation import validate_session_id

router = APIRouter()


def _storage_dir() -> Path:
    return Path(__file__).resolve().parents[4] / "storage"


def _write_json(path: Path, data: Dict[str, Any]):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def _require_session(session_id: str) -> Path:
    """Raise 404 if session directory does not exist."""
    sdir = _storage_dir() / session_id
    if not sdir.exists():
        raise HTTPException(status_code=404, detail="session not found")
    return sdir


@router.post("/session/job_description")
async def set_job_description(payload: Dict[str, Any]):
    """
    body: { "session_id", "job_role", "job_description", "company" }
    """
    session_id = payload.get("session_id")
    if not session_id:
        raise HTTPException(status_code=400, detail="session_id required")
    # BUG 3: Validate session_id is a UUID4 before any file I/O
    validate_session_id(session_id)

    sdir = _require_session(session_id)
    _write_json(sdir / "job_description.json", {
        "job_role":        payload.get("job_role", ""),
        "job_description": payload.get("job_description", ""),
        "company":         payload.get("company", ""),
    })
    return {"status": "ok"}


@router.post("/session/candidate_profile")
async def set_candidate_profile(payload: Dict[str, Any]):
    """
    body: { "session_id", "name", "expertise_level", "experience", "education" }
    expertise_level: "fresher" | "intermediate" | "experienced"
    """
    session_id = payload.get("session_id")
    if not session_id:
        raise HTTPException(status_code=400, detail="session_id required")
    # BUG 3: Validate session_id is a UUID4 before any file I/O
    validate_session_id(session_id)

    sdir  = _require_session(session_id)
    level = payload.get("expertise_level", "fresher").lower()
    if level not in ("fresher", "intermediate", "experienced"):
        level = "fresher"

    _write_json(sdir / "candidate_profile.json", {
        "name":            payload.get("name", ""),
        "expertise_level": level,
        "experience":      payload.get("experience", ""),
        "education":       payload.get("education", ""),
    })
    return {"status": "ok"}
