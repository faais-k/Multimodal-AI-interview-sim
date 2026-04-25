from fastapi import APIRouter, HTTPException
from pathlib import Path
import json
from typing import Any, Dict

from backend.app.core.storage import get_storage_dir
from backend.app.core.validation import validate_session_id

router = APIRouter()


def _storage_dir() -> Path:
    return get_storage_dir()


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


def _read_json(path: Path) -> dict:
    """Read JSON file, return empty dict on error."""
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


@router.get("/session/status/{session_id}")
async def get_session_status(session_id: str):
    """
    Get current interview status for state recovery after page refresh.
    """
    validate_session_id(session_id)
    sdir = _require_session(session_id)
    
    # FUNC-2: Check for expired sessions (older than 24 hours)
    state_file = sdir / "interview_state.json"
    if state_file.exists():
        import time
        last_modified = state_file.stat().st_mtime
        if time.time() - last_modified > 3600 * 24:  # 24 hours
            return {
                "status": "expired",
                "session_id": session_id,
                "has_active_question": False,
                "is_completed": False,
                "message": "Session expired after 24 hours of inactivity"
            }
    
    # Load interview state
    state = _read_json(sdir / "interview_state.json")
    plan = _read_json(sdir / "interview_plan.json")
    
    if not state:
        return {
            "status": "not_started",
            "session_id": session_id,
            "has_active_question": False,
            "is_completed": False
        }
    
    # Get current question info
    questions_asked = state.get("questions_asked", [])
    total_questions = plan.get("total_questions", len(questions_asked))
    
    # Find current unanswered question (last one in questions_asked)
    current_question = None
    has_active_question = False
    
    if questions_asked:
        last_asked = questions_asked[-1]
        last_id = last_asked.get("id")
        
        # Check if answered (answers is a DICT)
        answers = state.get("answers", {})
        if last_id not in answers:
            current_question = last_asked
            has_active_question = True
    
    return {
        "status": "active" if not state.get("completed") else "completed",
        "session_id": session_id,
        "current_question": current_question,
        "question_number": len(questions_asked),
        "total_questions": total_questions,
        "questions_asked_count": len(questions_asked),
        "stage": state.get("cursor", {}).get("stage", "intro"),
        "has_active_question": has_active_question,
        "is_completed": state.get("completed", False)
    }


@router.post("/session/skip/{session_id}")
async def skip_question(session_id: str, question_id: str = None):
    """
    Formally skip a question and advance the interview state.
    Safe even if interview_state.json is missing (returns 400 instead of 500).
    """
    validate_session_id(session_id)
    sdir = _require_session(session_id)
    
    from backend.app.core.interview_flow import read_state, write_state, get_state_lock
    
    try:
        async with get_state_lock(session_id):
            # Load state
            try:
                state = read_state(sdir, session_id)
            except FileNotFoundError:
                raise HTTPException(
                    status_code=400, 
                    detail="Interview has not been started yet. Call /api/session/start_interview first."
                )
            
            # Get question_id to skip (defaults to the latest asked question if not provided)
            if not question_id:
                questions_asked = state.get("questions_asked", [])
                if questions_asked:
                    question_id = questions_asked[-1].get("id")
            
            if not question_id:
                raise HTTPException(status_code=400, detail="No active question to skip")
            
            # Record the skip in answers (DICT)
            answers = state.setdefault("answers", {})
            
            # Find the question text
            q_text = "N/A"
            for q in state.get("questions_asked", []):
                if q.get("id") == question_id:
                    q_text = q.get("question", "N/A")
                    break

            skip_record = {
                "question": q_text,
                "answer": "[SKIPPED BY USER]",
                "score": 0.0, # Zero score for skipped
                "skipped": True,
                "time": __import__('datetime').datetime.utcnow().isoformat() + "Z"
            }
            
            answers[question_id] = skip_record
            
            # Advance cursor
            cursor = state.setdefault("cursor", {"stage": "intro"})
            cursor["last_question_id"] = question_id
            
            # Advance stage logic
            if not question_id.startswith("followup"):
                if cursor.get("stage") == "intro":
                    cursor["stage"] = "project"
                elif cursor.get("stage") == "project":
                    cursor["stage"] = "dynamic"
            
            # Completion check
            is_final = False
            for q in state.get("questions_asked", []):
                if q.get("id") == question_id and q.get("is_final"):
                    is_final = True
                    break
            
            if is_final or question_id.startswith("wrapup"):
                state["completed"] = True
                
            write_state(sdir, session_id, state)
            
        # Now call next_question to get the next question
        from backend.app.api.routes.session import next_question
        next_q_res = await next_question(session_id)
        
        return {
            "status": "skipped",
            "skipped_question_id": question_id,
            "next_question": next_q_res.get("question"),
            "total_questions": next_q_res.get("total_questions", 0)
        }
    except HTTPException:
        raise
    except Exception as e:
        import logging
        logging.error(f"Error skipping question for session {session_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Internal error during skip: {str(e)}")
