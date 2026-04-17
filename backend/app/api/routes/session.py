import asyncio
import json
import os
import uuid
from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from backend.app.core import interview_flow
from backend.app.core.validation import validate_session_id
from backend.app.core.db_ops import create_session_record, update_session_status

router = APIRouter(tags=["Session"])


def _storage_dir() -> Path:
    from backend.app.core.storage import get_storage_dir
    return get_storage_dir()


class SessionCreateResponse(BaseModel):
    session_id: str
    storage_path: str


@router.post("/session/create", response_model=SessionCreateResponse)
async def create_session():
    sid = str(uuid.uuid4())
    session_dir = _storage_dir() / sid
    os.makedirs(session_dir, exist_ok=True)
    (session_dir / "resumes").mkdir(exist_ok=True)
    (session_dir / "audio").mkdir(exist_ok=True)
    (session_dir / "text_answers").mkdir(exist_ok=True)
    await create_session_record(sid)
    return {"session_id": sid, "storage_path": str(session_dir)}


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

    # Guard: do not reinitialise if interview already has questions asked OR answers
    state_path = STORAGE_DIR / session_id / "interview_state.json"
    if state_path.exists():
        try:
            existing      = json.loads(state_path.read_text(encoding="utf-8"))
            has_answers   = bool(existing.get("answers"))
            has_questions = bool(existing.get("questions_asked"))
            if has_answers or has_questions:
                return {"status": "ok", "message": "interview already in progress"}
        except Exception:
            pass  # corrupt state file — fall through and reinitialise

    interview_flow.init_interview_state(STORAGE_DIR, session_id, parsed)
    await update_session_status(session_id, "active")
    return {"status": "ok", "message": "interview started"}


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
        q = interview_flow._decide_next_write(
            STORAGE_DIR, session_id, plan, decision, resolved_q_text
        )

    return {"status": "ok", "question": q}
