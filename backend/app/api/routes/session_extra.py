# backend/app/api/routes/session_extra.py
from fastapi import APIRouter, HTTPException
from pathlib import Path
import json
from typing import Dict, Any

router = APIRouter()

def _base_dir() -> Path:
    return Path(__file__).resolve().parents[5]

def _storage_dir() -> Path:
    return _base_dir() / "storage"

def _session_dir(session_id: str) -> Path:
    return _storage_dir() / session_id

def _write_json(path: Path, data: Dict[str, Any]):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")

@router.post("/session/job_description")
async def set_job_description(payload: Dict[str, Any]):
    """
    body: { "session_id": "...", "job_role": "...", "job_description": "..." }
    """
    session_id = payload.get("session_id")
    if not session_id:
        raise HTTPException(status_code=400, detail="session_id required")

    job_role = payload.get("job_role", "")
    job_description = payload.get("job_description", "")

    p = _session_dir(session_id) / "job_description.json"
    _write_json(p, {"job_role": job_role, "job_description": job_description})
    return {"status": "ok", "path": str(p)}

@router.post("/session/candidate_profile")
async def set_candidate_profile(payload: Dict[str, Any]):
    """
    body: { "session_id": "...", "experience": "long text or list", "education": "text or list" }
    """
    session_id = payload.get("session_id")
    if not session_id:
        raise HTTPException(status_code=400, detail="session_id required")

    experience = payload.get("experience", "")
    education = payload.get("education", "")

    p = _session_dir(session_id) / "candidate_profile.json"
    _write_json(p, {"experience": experience, "education": education})
    return {"status": "ok", "path": str(p)}

@router.post("/session/candidate_question")
async def candidate_question(payload: Dict[str, Any]):
    """
    Candidate can ask a question at wrapup.
    body: { "session_id": "...", "question_text": "..." }
    Returns a heuristic answer based on job_description + resume + plan.
    """
    session_id = payload.get("session_id")
    qtext = payload.get("question_text", "")
    if not session_id or not qtext:
        raise HTTPException(status_code=400, detail="session_id and question_text required")

    sdir = _session_dir(session_id)
    # load job description, resume, plan
    job_p = sdir / "job_description.json"
    parsed_p = sdir / "parsed_resume.json"
    plan_p = sdir / "interview_plan.json"
    profile_p = sdir / "candidate_profile.json"

    sources = []
    if job_p.exists():
        sources.append(json.loads(job_p.read_text(encoding="utf-8")))
    if parsed_p.exists():
        sources.append(json.loads(parsed_p.read_text(encoding="utf-8")))
    if profile_p.exists():
        sources.append(json.loads(profile_p.read_text(encoding="utf-8")))
    if plan_p.exists():
        plan = json.loads(plan_p.read_text(encoding="utf-8"))
        sources.append({"plan_summary": plan.get("summary", ""), "questions_count": plan.get("total_questions", 0)})

    # Very simple heuristic answer:
    qlower = qtext.lower()
    answer_parts = []
    # if candidate asks about role / responsibilities, answer with job_role snippet
    if job_p.exists():
        job = json.loads(job_p.read_text(encoding="utf-8"))
        jr = job.get("job_role","").strip()
        jd = job.get("job_description","").strip()
        if "role" in qlower or "responsibil" in qlower or "what i will do" in qlower:
            if jr:
                answer_parts.append(f"This role: {jr}.")
            if jd:
                # return first 350 chars of JD as answer context
                answer_parts.append(f"Job description summary: {jd[:350]}")

    # if asks about interview format / scoring
    if "score" in qlower or "scor" in qlower or "how will i be evaluated" in qlower:
        answer_parts.append("The interview is scored per question. Each question has a weight. The final score is a weighted average. Low answers can be flagged for human review.")

    # fallback: try to echo relevant keywords from resume
    if not answer_parts and parsed_p.exists():
        parsed = json.loads(parsed_p.read_text(encoding="utf-8"))
        skills = parsed.get("skills", [])[:8]
        summary = parsed.get("summary", "")
        if skills:
            answer_parts.append(f"Based on your resume, relevant areas include: {', '.join(skills)}.")
        if summary:
            answer_parts.append(f"Resume summary: {summary}")

    if not answer_parts:
        answer_parts.append("I don't have a specific answer from the stored data. If you want a more detailed answer, add the job description or resume to the session.")

    answer = " ".join(answer_parts)
    return {"status": "ok", "question": qtext, "answer": answer}
