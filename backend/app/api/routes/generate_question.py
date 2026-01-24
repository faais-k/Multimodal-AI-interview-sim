from fastapi import APIRouter, HTTPException
from pathlib import Path
import json
import uuid

router = APIRouter(tags=["Interview"])


def load_json(path: Path):
    if not path.exists():
        raise FileNotFoundError(f"File not found: {path}")
    return json.loads(path.read_text(encoding="utf-8", errors="ignore"))


@router.post("/interview/generate_question")
async def generate_question(payload: dict):
    """
    payload:
    {
      "session_id": "...",
      "job_role": "ML Engineer (optional)",
      "job_description": ".... (optional)"
    }
    """

    session_id = payload.get("session_id")
    if not session_id:
        raise HTTPException(status_code=400, detail="session_id required")

    BASE_DIR = Path(__file__).resolve().parents[4]
    STORAGE_DIR = BASE_DIR / "storage"
    session_dir = STORAGE_DIR / session_id

    if not session_dir.exists():
        raise HTTPException(status_code=404, detail="session_id not found")

    # Load parsed resume
    parsed_resume_path = session_dir / "parsed_resume.json"
    parsed = load_json(parsed_resume_path)

    # Load interview state
    state_path = session_dir / "interview_state.json"
    state = load_json(state_path)

    stage = state.get("cursor", {}).get("stage", "intro")

    # --------- RULE BASED MVP QUESTION GENERATION ----------
    # (Next step we will replace this with LLM generation)
    candidate_name = parsed.get("name", "there")
    skills = parsed.get("skills", []) or []
    projects = parsed.get("projects", []) or []

    # intro
    if stage == "intro":
        q = {
            "id": "intro_1",
            "type": "intro",
            "question": f"Hi {candidate_name}! Please introduce yourself briefly (education, skills, and what you're looking for)."
        }
        return {"status": "ok", "question": q}

    # project
    if stage == "project":
        if projects:
            q = {
                "id": "project_1",
                "type": "project",
                "question": "Can you explain one of your main projects? Focus on your role, what problem it solved, and the tech stack."
            }
        else:
            q = {
                "id": "project_1",
                "type": "project",
                "question": "I don’t see projects listed. Can you describe any internship/learning project you built and what you learned?"
            }
        return {"status": "ok", "question": q}

    # dynamic stage
    # pick next skill that was not asked yet
    asked = set([q["id"] for q in state.get("questions_asked", [])])

    for s in skills:
        qid = f"skill_{s}"
        if qid not in asked:
            q = {
                "id": qid,
                "type": "technical",
                "question": f"Can you explain your real-world experience with {s}? Mention a project where you used it."
            }
            return {"status": "ok", "question": q}

    # fallback end
    q = {
        "id": f"end_{uuid.uuid4().hex[:6]}",
        "type": "end",
        "question": "That’s all from my side. Do you have any questions for me?"
    }
    return {"status": "ok", "question": q}
