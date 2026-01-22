# backend/app/core/interview_flow.py
from pathlib import Path
import json
import uuid
from typing import Dict, Any, Optional

STEPS = [
    "self_intro",
    "project_probe",
    "role_probe",
    "skill_probe",
    "project_detail",
    "followups",
    "wrapup"
]

def _load(session_dir: Path, name: str):
    p = session_dir / name
    if not p.exists():
        return None
    return json.loads(p.read_text(encoding="utf-8"))

def _save(session_dir: Path, name: str, obj):
    p = session_dir / name
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(obj, ensure_ascii=False, indent=2))

def init_interview_state(storage_dir: Path, session_id: str, parsed_resume: dict):
    session_dir = storage_dir / session_id
    state = {
        "session_id": session_id,
        "step_index": 0,
        "history": [],  # list of {question_id, question, answer, timestamp}
        "context": {
            "has_projects": bool(parsed_resume.get("projects")),
            "has_work_experience": False,  # optionally derive from resume
            "detected_skills": parsed_resume.get("skills", []),
            "resume_summary": parsed_resume.get("summary", "")
        }
    }
    _save(session_dir, "interview_state.json", state)
    return state

def get_state(storage_dir: Path, session_id: str) -> Optional[dict]:
    session_dir = storage_dir / session_id
    return _load(session_dir, "interview_state.json")

def persist_state(storage_dir: Path, session_id: str, state: dict):
    session_dir = storage_dir / session_id
    _save(session_dir, "interview_state.json", state)

def decide_next_question(storage_dir: Path, session_id: str, plan: dict) -> dict:
    """
    Returns a question object from plan and updates the state.
    Logic:
      - first: self_intro
      - second: project_probe if projects else role_probe or skill_probe
      - afterwards: drill into project details and then followups (based on previous answers)
    """
    session_dir = storage_dir / session_id
    state = get_state(storage_dir, session_id)
    if state is None:
        # try to initialize using parsed resume
        parsed = _load(session_dir, "parsed_resume.json") or {}
        state = init_interview_state(storage_dir, session_id, parsed)

    step_idx = state.get("step_index", 0)
    # Helper to find question by id or by type/skill in plan
    questions = plan.get("questions", [])

    # STEP 0: self introduction question
    if step_idx == 0:
        q = next((q for q in questions if q.get("id") == "intro"), None)
        if not q:
            q = {"id": "intro", "type": "hr", "question": "Please introduce yourself briefly."}
        # update state
        state["step_index"] += 1
        persist_state(storage_dir, session_id, state)
        return q

    # STEP 1: project_probe or role_probe or skill_probe
    if step_idx == 1:
        if state["context"].get("has_projects"):
            q = {"id": "project_probe", "type": "hr", "question": "Tell me about your most important project."}
        elif state["context"].get("has_work_experience"):
            q = {"id": "role_probe", "type": "hr", "question": "Describe your previous role and responsibilities."}
        else:
            # fallback: ask about top skill from parsed resume
            skill = state["context"].get("detected_skills", ["technical"])[0]
            q = {"id": f"skill_probe_{skill}", "type": "technical", "skill": skill, "question": f"Tell me about your experience with {skill}."}
        state["step_index"] += 1
        persist_state(storage_dir, session_id, state)
        return q

    # STEP 2+: contextual drill down: choose a question from plan matching project/skill
    # Very simple heuristic: prefer technical questions matching resume skills
    for q in questions:
        # skip already asked
        if any(h.get("question_id") == q.get("id") for h in state["history"]):
            continue
        if q.get("type") == "technical" and q.get("skill") in state["context"].get("detected_skills", []):
            # ask this
            state["history"].append({"question_id": q.get("id"), "question": q.get("question"), "asked_at": None})
            state["step_index"] += 1
            persist_state(storage_dir, session_id, state)
            return q

    # if nothing found, return a generic followup
    q = {"id": str(uuid.uuid4()), "type": "hr", "question": "Can you describe a challenge you solved recently?"}
    state["history"].append({"question_id": q.get("id"), "question": q.get("question"), "asked_at": None})
    state["step_index"] += 1
    persist_state(storage_dir, session_id, state)
    return q

def record_answer(storage_dir: Path, session_id: str, question_id: str, question_text: str, answer_text: str, score=None):
    session_dir = storage_dir / session_id
    state = get_state(storage_dir, session_id) or {}
    entry = {
        "question_id": question_id,
        "question": question_text,
        "answer": answer_text,
        "score": score,
        "timestamp": __import__("datetime").datetime.utcnow().isoformat() + "Z"
    }
    state.setdefault("history", []).append(entry)
    persist_state(storage_dir, session_id, state)
    return state
