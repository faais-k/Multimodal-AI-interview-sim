from fastapi import APIRouter, HTTPException
from pathlib import Path
import json
from datetime import datetime
from typing import Any, Dict

from backend.app.core.storage import get_storage_dir, write_json_atomic
from backend.app.core.validation import validate_session_id
from backend.app.core.rate_limit import check_rate_limit

router = APIRouter()


def _storage_dir() -> Path:
    return get_storage_dir()


def _write_json(path: Path, data: Dict[str, Any]):
    write_json_atomic(path, data)


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
    # Rate limit: 30 requests per minute per session
    allowed = await check_rate_limit(session_id, "get_session_status", max_requests=30, window_seconds=60)
    if not allowed:
        raise HTTPException(status_code=429, detail="Too many status checks. Please wait.")

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
                storage = get_storage_dir()
                state = read_state(storage, session_id)
            except FileNotFoundError:
                raise HTTPException(
                    status_code=400, 
                    detail="Interview has not been started yet. Call /api/session/start_interview first."
                )
            
            # Get question_id to skip (defaults to the latest asked question if not provided)
            questions_asked = state.get("questions_asked", [])
            if not question_id:
                if questions_asked:
                    question_id = questions_asked[-1].get("id")
            
            if not question_id:
                raise HTTPException(status_code=400, detail="No active question to skip")

            answers = state.setdefault("answers", {})
            if question_id in answers:
                raise HTTPException(status_code=409, detail="Question has already been answered or skipped")
            
            # Find the active question being skipped.
            asked_question = None
            for q in questions_asked:
                if q.get("id") == question_id:
                    asked_question = q
                    break
            if not asked_question:
                raise HTTPException(status_code=404, detail="Question not found in interview state")

            skip_record = {
                "question": asked_question.get("question", "N/A"),
                "answer": "Skipped",
                "score": None,
                "skipped": True,
                "time": datetime.utcnow().isoformat() + "Z"
            }
            
            answers[question_id] = skip_record
            state.setdefault("turns", []).append({
                "role": "candidate",
                "id": question_id,
                "text": "Skipped",
                "score": None,
                "skipped": True,
                "time": skip_record["time"],
            })
            
            # Advance cursor
            cursor = state.setdefault("cursor", {"stage": "intro"})
            cursor["last_question_id"] = question_id
            
            # Advance stage logic
            if not question_id.startswith("followup"):
                if cursor.get("stage") == "intro":
                    cursor["stage"] = "project"
                elif cursor.get("stage") == "project":
                    cursor["stage"] = "technical"
            
            # Completion check
            is_final = False
            for q in state.get("questions_asked", []):
                if q.get("id") == question_id and q.get("is_final"):
                    is_final = True
                    break
            
            if is_final or question_id.startswith("wrapup"):
                state["completed"] = True
                
            write_state(storage, session_id, state)
            
            from backend.app.core import interview_flow

            plan = _read_json(storage / session_id / "interview_plan.json")
            decision = interview_flow._decide_next_read(storage, session_id, plan)
            resolved_q_text = decision.get("cached_q_text") if decision.get("action") == "followup" else None
            if decision.get("action") == "followup" and resolved_q_text is None:
                topic = (decision.get("original_q") or {}).get("skill_target") or "this area"
                resolved_q_text = (
                    f"Could you give me a concrete example of working with {topic}?"
                    if decision.get("depth", 1) <= 1
                    else f"What was the most difficult problem you solved with {topic}?"
                )

            next_q = interview_flow._decide_next_write(
                storage, session_id, plan, decision, resolved_q_text
            )

            if isinstance(next_q, dict) and "id" in next_q:
                next_question = next_q
                next_status = "skipped"
            else:
                next_question = None
                next_status = next_q.get("status", "completed") if isinstance(next_q, dict) else "completed"
        
        return {
            "status": next_status,
            "skipped_question_id": question_id,
            "next_question": next_question,
            "total_questions": plan.get("total_questions", 0)
        }
    except HTTPException:
        raise
    except Exception as e:
        import logging
        logging.error(f"Error skipping question for session {session_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Internal error during skip: {str(e)}")
