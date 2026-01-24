# backend/app/core/interview_flow.py
import json
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, Any, List

STATE_FILE = "interview_state.json"


def _session_dir(storage_dir: Path, session_id: str) -> Path:
    return Path(storage_dir) / session_id


def _state_path(storage_dir: Path, session_id: str) -> Path:
    return _session_dir(storage_dir, session_id) / STATE_FILE


def _now():
    return datetime.utcnow().isoformat() + "Z"


def read_state(storage_dir: Path, session_id: str) -> Dict[str, Any]:
    p = _state_path(storage_dir, session_id)
    if not p.exists():
        raise FileNotFoundError("interview_state.json not found. Call start_interview first.")
    return json.loads(p.read_text(encoding="utf-8"))


def write_state(storage_dir: Path, session_id: str, state: Dict[str, Any]):
    p = _state_path(storage_dir, session_id)
    p.write_text(json.dumps(state, indent=2, ensure_ascii=False), encoding="utf-8")


def init_interview_state(storage_dir: Path, session_id: str, parsed_resume: dict, job_role: Optional[str] = None):
    """
    Creates interview_state.json and sets stage = intro
    """
    session_dir = _session_dir(storage_dir, session_id)
    session_dir.mkdir(parents=True, exist_ok=True)

    state = {
        "session_id": session_id,
        "job_role": job_role,
        "candidate": {
            "name": parsed_resume.get("name"),
            "email": parsed_resume.get("email"),
            "skills": parsed_resume.get("skills", []),
            "projects": parsed_resume.get("projects", []),
            "summary": parsed_resume.get("summary", "")
        },
        "cursor": {
            "stage": "intro",
            "last_question_id": None,
            "current_topic": None
        },

        "questions_asked": [],
        "answers": {},
        "turns": []
    }

    write_state(storage_dir, session_id, state)
    return state


def record_answer(
    storage_dir: Path,
    session_id: str,
    question_id: str,
    question_text: str,
    answer_text: str,
    score: Optional[float] = None
):
    """
    Stores answer + score into interview_state.json
    """
    state = read_state(storage_dir, session_id)

    state["answers"][question_id] = {
        "question": question_text,
        "answer": answer_text,
        "score": score,
        "time": _now()
    }

    state["turns"].append({
    "role": "candidate",
    "id": question_id,
    "text": answer_text,
    "score": score,
    "time": _now()
})


    # move stage forward after intro and project
    if state["cursor"]["stage"] == "intro":
        state["cursor"]["stage"] = "project"
    elif state["cursor"]["stage"] == "project":
        state["cursor"]["stage"] = "dynamic"

    state["cursor"]["last_question_id"] = question_id
    write_state(storage_dir, session_id, state)
    return True


def _make_question(qid: str, qtype: str, question: str, meta: Optional[dict] = None):
    return {
        "id": qid,
        "type": qtype,
        "question": question,
        "meta": meta or {}
    }


def decide_next_question(storage_dir: Path, session_id: str, plan: dict) -> Dict[str, Any]:
    """
    Dynamic question selection (MVP):
    - Intro
    - Project overview
    - Then skill-based dynamic questions (not fixed order)
    """
    state = read_state(storage_dir, session_id)
    stage = state["cursor"]["stage"]

    candidate_name = state["candidate"].get("name") or "there"
    projects = state["candidate"].get("projects", []) or []
    skills = state["candidate"].get("skills", []) or []

    # 1) Intro
    if stage == "intro":
        q = _make_question(
            qid="intro_1",
            qtype="intro",
            question=f"Hi {candidate_name}! Please introduce yourself briefly (education, skills, and what you're looking for)."
        )
        state["questions_asked"].append({"id": q["id"], "question": q["question"], "time": _now()})
        state["turns"].append({
            "role": "interviewer",
            "id": q["id"],
            "text": q["question"],
            "time": _now()
        })

        write_state(storage_dir, session_id, state)
        return q

    # 2) Project overview
    if stage == "project":
        if projects:
            q = _make_question(
                qid="project_1",
                qtype="project",
                question="Can you explain one of your main projects? Focus on your role, what problem it solved, and the tech stack."
            )
        else:
            q = _make_question(
                qid="project_1",
                qtype="project",
                question="You don’t seem to have projects listed. Can you explain any work you’ve done (internship/mini-project/learning project)?"
            )
        state["questions_asked"].append({"id": q["id"], "question": q["question"], "time": _now()})
        state["turns"].append({
            "role": "interviewer",
            "id": q["id"],
            "text": q["question"],
            "time": _now()
        })
        write_state(storage_dir, session_id, state)
        return q

    # 3) Dynamic stage: pick next unasked skill question from plan
    asked_ids = {q["id"] for q in state["questions_asked"]}
    plan_questions = plan.get("questions", [])

    # prefer technical questions
    for q in plan_questions:
        if q.get("id") not in asked_ids:
            state["questions_asked"].append({"id": q["id"], "question": q.get("question"), "time": _now()})
            state["turns"].append({
                "role": "interviewer",
                "id": q["id"],
                "text": q["question"],
                "time": _now()
            })
            write_state(storage_dir, session_id, state)
            return q

    # fallback end
    q = _make_question(
        qid="end_1",
        qtype="end",
        question="That’s all from my side. Do you have any questions for me?"
    )
    state["questions_asked"].append({"id": q["id"], "question": q["question"], "time": _now()})
    state["turns"].append({
            "role": "interviewer",
            "id": q["id"],
            "text": q["question"],
            "time": _now()
        })
    write_state(storage_dir, session_id, state)
    return q

def advance_stage(storage_dir: Path, session_id: str, current_question_id: str):
    state = read_state(storage_dir, session_id)

    stage = state.get("cursor", {}).get("stage", "intro")

    # move stages forward
    if stage == "intro":
        state["cursor"]["stage"] = "project"
    elif stage == "project":
        state["cursor"]["stage"] = "dynamic"
    # dynamic stays dynamic (we don't auto-finish here)

    state["cursor"]["last_question_id"] = current_question_id

    write_state(storage_dir, session_id, state)
    return state["cursor"]["stage"]

