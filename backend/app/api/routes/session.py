import asyncio
import json
import os
import uuid
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request, Depends
from pydantic import BaseModel

from backend.app.core import interview_flow
from backend.app.core.rate_limit import check_rate_limit
from backend.app.core.validation import validate_session_id
from backend.app.core.db_ops import create_session_record, update_session_status
from backend.app.core.auth import get_optional_user
from backend.app.models.session import SessionStatus

router = APIRouter(tags=["Session"])


def _storage_dir() -> Path:
    from backend.app.core.storage import get_storage_dir

    return get_storage_dir()


class SessionCreateResponse(BaseModel):
    session_id: str


@router.post("/session/create", response_model=SessionCreateResponse)
async def create_session(request: Request, user: dict = Depends(get_optional_user)):
    client_ip = request.client.host if request.client else "unknown"
    allowed = await check_rate_limit(
        client_ip,
        "session_create",
        max_requests=10,
        window_seconds=3600,
    )
    if not allowed:
        raise HTTPException(
            status_code=429,
            detail="Too many sessions from this IP. Try again in an hour.",
        )

    sid = str(uuid.uuid4())
    session_dir = _storage_dir() / sid
    os.makedirs(session_dir, exist_ok=True)
    (session_dir / "resumes").mkdir(exist_ok=True)
    (session_dir / "audio").mkdir(exist_ok=True)
    (session_dir / "text_answers").mkdir(exist_ok=True)

    uid = user.get("uid") if user else None
    await create_session_record(sid, user_id=uid)
    return {"session_id": sid}


@router.post("/session/start_interview")
async def start_interview(session_id: str):
    # BUG 3: Validate session_id is a UUID4 before any file I/O
    validate_session_id(session_id)

    STORAGE_DIR = _storage_dir()
    parsed_path = STORAGE_DIR / session_id / "parsed_resume.json"
    if not parsed_path.exists():
        raise HTTPException(
            status_code=404,
            detail="parsed_resume.json not found. Call /api/parse/resume first.",
        )

    parsed = json.loads(parsed_path.read_text(encoding="utf-8"))

    # LOGIC-1 FIX: Lock the check-and-init to prevent race conditions from
    # double-clicks. Without this, two requests can both pass the exists()
    # check before either writes, corrupting state.
    # SAFETY NET: Also ensure interview_plan.json exists under lock to prevent
    # duplicate plan generation from concurrent requests.
    async with interview_flow.get_state_lock(session_id):
        # Check and generate plan under lock to prevent race conditions
        plan_path = STORAGE_DIR / session_id / "interview_plan.json"
        if not plan_path.exists():
            from backend.app.api.routes.interview_plan import create_interview_plan

            await create_interview_plan(session_id)
        state_path = STORAGE_DIR / session_id / "interview_state.json"
        if state_path.exists():
            try:
                existing = json.loads(state_path.read_text(encoding="utf-8"))
                has_answers = bool(existing.get("answers"))
                has_questions = bool(existing.get("questions_asked"))
                if has_answers or has_questions:
                    return {"status": "ok", "message": "interview already in progress"}
            except Exception:
                pass  # corrupt state file — fall through and reinitialise

        interview_flow.init_interview_state(STORAGE_DIR, session_id, parsed)

    await update_session_status(session_id, SessionStatus.QUESTION_ACTIVE)
    return {"status": "ok", "message": "interview started"}


def _question_was_answered(state: dict, question_id: str) -> bool:
    """Check if a question has been answered or formally skipped."""
    if not question_id:
        return True
    answers = state.get("answers", {})
    return question_id in answers


def _get_current_question(state: dict) -> dict:
    """Get the latest asked question if it hasn't been answered yet."""
    questions_asked = state.get("questions_asked", [])
    if not questions_asked:
        return None

    # Check the very last question that was served to the user
    last_asked = questions_asked[-1]
    last_id = last_asked.get("id")

    if not _question_was_answered(state, last_id):
        return last_asked

    return None


@router.post("/session/next_question")
async def next_question(session_id: str):
    # BUG 3: Validate session_id is a UUID4 before any file I/O
    validate_session_id(session_id)

    STORAGE_DIR = _storage_dir()
    plan_path = STORAGE_DIR / session_id / "interview_plan.json"
    if not plan_path.exists():
        raise HTTPException(
            status_code=404,
            detail="interview_plan.json not found. Call /api/interview/plan first.",
        )
    plan = json.loads(plan_path.read_text(encoding="utf-8"))

    # BUG 2 fix: split lock into two narrow scopes with LLM generation outside.

    # SCOPE 1: Read state and determine action — fast, no LLM calls, no writes
    async with interview_flow.get_state_lock(session_id):
        # ── IDEMPOTENCY CHECK (Inside Lock) ───────────────────────────────────
        # Move inside lock to prevent race conditions where next_question reads
        # while score_text is still writing the answer.
        state = interview_flow.read_state(STORAGE_DIR, session_id)
        current_q = _get_current_question(state)
        if current_q:
            return {
                "status": "ok",
                "question": current_q,
                "total_questions": plan.get("total_questions", 0),
                "idempotent": True,
            }
        # ── END IDEMPOTENCY CHECK ─────────────────────────────────────────────

        decision = interview_flow._decide_next_read(STORAGE_DIR, session_id, plan)

    # Resolve follow-up question text OUTSIDE the lock (may call LLM, 2-4s)
    resolved_q_text = None
    if decision["action"] == "followup":
        # Use cached text if available (pre-generated at plan creation time)
        resolved_q_text = decision.get("cached_q_text")

        # Cache miss: call LLM in a thread — no event loop blocking
        if resolved_q_text is None:
            resolved_q_text = await asyncio.to_thread(
                interview_flow._llm_generate_followup,
                decision["original_q"]["question"],
                decision["last_answer"],
                decision["what_was_missing"],
                decision["original_q"].get("skill_target", ""),
                decision["depth"],
            )

        # Template fallback if LLM failed or is unavailable
        if resolved_q_text is None:
            topic = decision["original_q"].get("skill_target", "this area")
            resolved_q_text = (
                f"Could you give me a concrete example of working with {topic}?"
                if decision["depth"] <= 1
                else f"What was the most difficult problem you solved with {topic}?"
            )

    # SCOPE 2: Write question to state — fast, no LLM calls
    async with interview_flow.get_state_lock(session_id):
        res = interview_flow._decide_next_write(
            STORAGE_DIR, session_id, plan, decision, resolved_q_text
        )

    # ── Fix Problem 2: Ensure status updates are top-level ─────────────────────
    # If res is a status/completion object (no 'id' field), promote its status.
    if isinstance(res, dict) and "status" in res and "id" not in res:
        return {
            "status": res["status"],
            "message": res.get("message", ""),
            "question": None,
            "total_questions": plan.get("total_questions", 0),
        }

    return {"status": "ok", "question": res, "total_questions": plan.get("total_questions", 0)}
