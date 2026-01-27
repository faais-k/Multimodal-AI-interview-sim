import json
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, Any, List

from backend.app.core.interview_reasoning import detect_topic

STATE_FILE = "interview_state.json"


# ───────────────────────────
# Helpers
# ───────────────────────────

def _session_dir(storage_dir: Path, session_id: str) -> Path:
    return storage_dir / session_id


def _state_path(storage_dir: Path, session_id: str) -> Path:
    return _session_dir(storage_dir, session_id) / STATE_FILE


def _now() -> str:
    return datetime.utcnow().isoformat() + "Z"


def read_state(storage_dir: Path, session_id: str) -> Dict[str, Any]:
    path = _state_path(storage_dir, session_id)
    if not path.exists():
        raise FileNotFoundError("interview_state.json not found. Call start_interview first.")
    return json.loads(path.read_text(encoding="utf-8"))


def write_state(storage_dir: Path, session_id: str, state: Dict[str, Any]):
    path = _state_path(storage_dir, session_id)
    path.write_text(json.dumps(state, indent=2, ensure_ascii=False), encoding="utf-8")


def _last_candidate_turn(state: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    for turn in reversed(state.get("turns", [])):
        if turn.get("role") == "candidate":
            return turn
    return None


def _store_question(state: Dict[str, Any], q: Dict[str, Any]):
    state["questions_asked"].append({
        "id": q["id"],
        "question": q["question"],
        "time": _now()
    })
    state["turns"].append({
        "role": "interviewer",
        "id": q["id"],
        "text": q["question"],
        "time": _now()
    })


# ───────────────────────────
# Init
# ───────────────────────────

def init_interview_state(
    storage_dir: Path,
    session_id: str,
    parsed_resume: dict,
    job_role: Optional[str] = None
):
    session_dir = _session_dir(storage_dir, session_id)
    session_dir.mkdir(parents=True, exist_ok=True)

    state = {
        "session_id": session_id,
        "job_role": job_role,
        "completed": False,
        "candidate": {
            "name": parsed_resume.get("name"),
            "email": parsed_resume.get("email"),
            "skills": parsed_resume.get("skills", []),
            "projects": parsed_resume.get("projects", []),
            "summary": parsed_resume.get("summary", "")
        },
        "cursor": {
            "stage": "intro",            # intro → project → dynamic
            "last_question_id": None,
            "current_topic": None
        },
        "questions_asked": [],
        "answers": {},
        "turns": []
    }

    write_state(storage_dir, session_id, state)
    return state


# ───────────────────────────
# Recording answers
# ───────────────────────────

def record_answer(
    storage_dir: Path,
    session_id: str,
    question_id: str,
    question_text: str,
    answer_text: str,
    score: Optional[float] = None
):
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

    # topic detection
    topic = detect_topic(
        last_answer=answer_text,
        skills=state["candidate"].get("skills", []),
        projects=state["candidate"].get("projects", [])
    )

    if topic:
        state["cursor"]["current_topic"] = topic

    # stage transition
    if state["cursor"]["stage"] == "intro":
        state["cursor"]["stage"] = "project"
    elif state["cursor"]["stage"] == "project":
        state["cursor"]["stage"] = "dynamic"

    state["cursor"]["last_question_id"] = question_id
    if question_id.startswith("wrapup"):
        state["completed"] = True
    write_state(storage_dir, session_id, state)
    return True


# ───────────────────────────
# Follow-up logic
# ───────────────────────────

def should_ask_followup(state: Dict[str, Any]) -> bool:
    last_turn = _last_candidate_turn(state)
    if not last_turn:
        return False

    score = last_turn.get("score")
    text = last_turn.get("text", "")

    if score is not None and score < 6.5:
        return True

    if len(text.split()) < 30:
        return True

    return False


def generate_followup_question(state: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    topic = state["cursor"].get("current_topic")
    if not topic:
        return None

    asked = {t["text"].lower() for t in state["turns"] if t["role"] == "interviewer"}

    templates = [
        f"You mentioned {topic}. What was the biggest challenge you faced while working with it?",
        f"How did you apply {topic} in a real-world project?",
        f"What design or architectural decisions did you make when using {topic}?",
        f"If you had to improve your work with {topic}, what would you change?",
        f"You briefly mentioned {topic}. Can you walk me through your exact role and responsibilities?"
    ]

    for q in templates:
        if q.lower() not in asked:
            return {
                "id": f"followup_{topic}_{len(state['turns'])}",
                "type": "followup",
                "question": q,
                "meta": {"topic": topic}
            }

    return None


# ───────────────────────────
# Question factory
# ───────────────────────────

def _make_question(qid: str, qtype: str, question: str, meta: Optional[dict] = None):
    return {
        "id": qid,
        "type": qtype,
        "question": question,
        "meta": meta or {}
    }


# ───────────────────────────
# Main decision engine
# ───────────────────────────

def decide_next_question(storage_dir: Path, session_id: str, plan: dict) -> Dict[str, Any]:
    state = read_state(storage_dir, session_id)
    stage = state["cursor"]["stage"]

    if state.get("completed"):
        return {
            "status": "completed",
            "message": "Interview has ended. Thank you."
        }


    # ALWAYS defined (fixes your 500 error)
    name = state["candidate"].get("name") or "there"
    projects = state["candidate"].get("projects", [])

    # 1️⃣ Follow-up has absolute priority
    if should_ask_followup(state):
        q = generate_followup_question(state)
        if q:
            _store_question(state, q)
            write_state(storage_dir, session_id, state)
            return q

    # 2️⃣ Intro (only once)
    if stage == "intro":
        q = _make_question(
            "intro_1",
            "intro",
            f"Hi {name}! Please introduce yourself briefly — education, skills, and what you're looking for."
        )
        _store_question(state, q)
        write_state(storage_dir, session_id, state)
        return q

    # 3️⃣ Project
    if stage == "project":
        text = (
            "Can you explain one of your main projects — your role, the problem it solved, and the technologies you used?"
            if projects else
            "You don’t seem to have major projects listed. Can you explain any internship, mini-project, or learning project you’ve worked on?"
        )
        q = _make_question("project_1", "project", text)
        _store_question(state, q)
        write_state(storage_dir, session_id, state)
        return q

    # 4️⃣ Technical questions from plan
    asked_ids = {q["id"] for q in state["questions_asked"]}
    for q in plan.get("questions", []):
        if q.get("id") not in asked_ids:
            _store_question(state, q)
            write_state(storage_dir, session_id, state)
            return q

    # 5️⃣ Wrap-up (ONLY ONCE)
    if not state.get("completed"):
        q = _make_question(
            f"wrapup_{len(state['questions_asked'])}",
            "wrapup",
            "Before we wrap up, is there anything else you'd like to share or clarify about your experience?"
        )
        _store_question(state, q)
        write_state(storage_dir, session_id, state)
        return q

# -----------------------------------------------------------------------------------------------------------
# removed code 🔽

# # ───────────────────────────
# # Scoring helper
# # ───────────────────────────

# def get_question_context(storage_dir: Path, session_id: str, question_id: str):
#     if question_id.startswith("intro"):
#         return "self_intro", {}
#     if question_id.startswith("project"):
#         return "project", {}
#     if question_id.startswith("followup"):
#         return "followup", {}
#     return "technical", {}
