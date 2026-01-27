from fastapi import APIRouter, HTTPException
from pathlib import Path
import json
import uuid

router = APIRouter()

@router.post("/interview/plan/{session_id}")
async def create_interview_plan(session_id: str):
    """
    Create an interview plan based on parsed resume
    """
    BASE_DIR = Path(__file__).resolve().parents[4]
    STORAGE_DIR = BASE_DIR / "storage"

    parsed_file = STORAGE_DIR / session_id / "parsed_resume.json"

    if not parsed_file.exists():
        raise HTTPException(status_code=404, detail="Parsed resume not found")

    parsed = json.loads(parsed_file.read_text())

    skills = parsed.get("skills", [])
    summary = parsed.get("summary", "")
    name = parsed.get("name", "Candidate")

    questions = []

    # # --- Self Introduction ---
    # questions.append({
    #     "id": "intro",
    #     "type": "hr",
    #     "question": f"Hi {name}, please introduce yourself and briefly explain your background."
    # })

    # --- Skill-based technical questions ---
    for skill in skills[:5]:  # limit to 5 for now
        questions.append({
            "id": str(uuid.uuid4()),
            "type": "technical",
            "skill": skill,
            "question": f"Can you explain your experience with {skill}?"
        })

    # --- Behavioral ---
    questions.append({
        "id": "behavioral",
        "type": "hr",
        "question": "Describe a challenging problem you faced and how you solved it."
    })

    plan = {
        "session_id": session_id,
        "candidate": name,
        "summary": summary,
        "total_questions": len(questions),
        "questions": questions
    }

    out_file = STORAGE_DIR / session_id / "interview_plan.json"
    out_file.write_text(json.dumps(plan, indent=2))

    return {
        "status": "ok",
        "total_questions": len(questions),
        "plan_path": str(out_file)
    }
