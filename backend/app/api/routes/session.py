from pydantic import BaseModel
import uuid
import os
from pathlib import Path
from fastapi import APIRouter, HTTPException
import json

from backend.app.core import interview_flow

router = APIRouter(tags=["Session"])

STORAGE_ROOT = Path.cwd() / "storage"


class SessionCreateResponse(BaseModel):
    session_id: str
    storage_path: str


@router.post("/session/create", response_model=SessionCreateResponse)
async def create_session():
    sid = str(uuid.uuid4())
    session_dir = STORAGE_ROOT / sid
    os.makedirs(session_dir, exist_ok=True)
    (session_dir / "resumes").mkdir(exist_ok=True)
    (session_dir / "audio").mkdir(exist_ok=True)
    (session_dir / "text_answers").mkdir(exist_ok=True)
    return {"session_id": sid, "storage_path": str(session_dir)}


@router.post("/session/start_interview")
async def start_interview(session_id: str):
    BASE_DIR = Path(__file__).resolve().parents[4]
    STORAGE_DIR = BASE_DIR / "storage"

    parsed_path = STORAGE_DIR / session_id / "parsed_resume.json"
    if not parsed_path.exists():
        raise HTTPException(status_code=404, detail="parsed_resume.json not found. Parse resume first.")

    parsed = json.loads(parsed_path.read_text(encoding="utf-8"))
    interview_flow.init_interview_state(STORAGE_DIR, session_id, parsed)
    return {"status": "ok", "message": "interview started"}


@router.post("/session/next_question")
async def next_question(session_id: str):
    BASE_DIR = Path(__file__).resolve().parents[4]
    STORAGE_DIR = BASE_DIR / "storage"

    plan_path = STORAGE_DIR / session_id / "interview_plan.json"
    if not plan_path.exists():
        raise HTTPException(status_code=404, detail="interview_plan.json not found")

    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    q = interview_flow.decide_next_question(STORAGE_DIR, session_id, plan)
    return {"status": "ok", "question": q}
