# backend/app/api/routes/interview_plan.py
from fastapi import APIRouter, HTTPException
from pathlib import Path
import json, uuid
from typing import List, Dict
import re
from collections import Counter

router = APIRouter()

STOPWORDS = {
    "the","and","for","with","that","this","from","your","you","are","will","have",
    "has","use","using","a","an","in","on","to","of","is","it","as","by","be","or"
}

def _base_dir() -> Path:
    return Path(__file__).resolve().parents[5]

def _storage_dir() -> Path:
    return _base_dir() / "storage"

def _session_path(session_id: str) -> Path:
    return _storage_dir() / session_id

def _read_json(p: Path):
    return json.loads(p.read_text(encoding="utf-8"))

def _write_json(p: Path, data):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data, indent=2), encoding="utf-8")

def extract_keywords(text: str, top_k: int = 12) -> List[str]:
    if not text:
        return []
    # simple tokenization + filter
    tokens = re.findall(r"[a-zA-Z0-9\-\_]{3,}", text.lower())
    tokens = [t for t in tokens if t not in STOPWORDS and not t.isdigit()]
    if not tokens:
        return []
    freq = Counter(tokens)
    common = [w for w,_ in freq.most_common(top_k)]
    return common

@router.post("/interview/plan/{session_id}")
async def create_interview_plan(session_id: str):
    """
    Create a richer interview plan using resume + job role/JD + experience + education.
    Flow enforced:
      - (intro fixed)
      - (project fixed)
      - technical / scenario questions (derived from skills + JD + experience)
      - HR behavioral
      - critical thinking / quick problem solving
      - warmup/ending / wrapup
    """
    storage = _storage_dir()
    sdir = _session_path(session_id)
    if not sdir.exists():
        raise HTTPException(status_code=404, detail="session not found")

    parsed_p = sdir / "parsed_resume.json"
    if not parsed_p.exists():
        raise HTTPException(status_code=404, detail="parsed resume not found")
    parsed = _read_json(parsed_p)
    skills = parsed.get("skills", [])  # list

    # optional extras
    jd_p = sdir / "job_description.json"
    profile_p = sdir / "candidate_profile.json"

    job_role = ""
    job_description = ""
    if jd_p.exists():
        jd = _read_json(jd_p)
        job_role = jd.get("job_role", "") or ""
        job_description = jd.get("job_description", "") or ""

    experience_text = ""
    education_text = ""
    if profile_p.exists():
        prof = _read_json(profile_p)
        experience_text = prof.get("experience", "") or ""
        education_text = prof.get("education", "") or ""

    # combine texts and extract keywords
    combined_text = " ".join([job_role, job_description, experience_text, education_text, parsed.get("summary","")])
    jd_keywords = extract_keywords(combined_text, top_k=10)
    resume_keywords = [s.lower() for s in skills[:8]]
    experience_keywords = extract_keywords(experience_text, top_k=6)
    education_keywords = extract_keywords(education_text, top_k=6)

    # build questions list (skip intro/project; interview_flow will ask them)
    questions = []

    # 1) Technical questions: produce one per skill + some scenario questions from JD keywords
    tech_sources = list(dict.fromkeys(resume_keywords + jd_keywords + experience_keywords))  # preserve order, unique
    for i, t in enumerate(tech_sources[:8]):
        questions.append({
            "id": str(uuid.uuid4()),
            "type": "technical",
            "skill": t,
            "question": f"Can you explain your experience with {t}? Include where you used it, your role, and a concrete outcome if available."
        })

    # 2) Scenario / design questions from job description keywords (deeper)
    for k in jd_keywords[:3]:
        questions.append({
            "id": str(uuid.uuid4()),
            "type": "technical",
            "skill": k,
            "question": f"Given the role '{job_role}', how would you design or architect a solution for {k} in a production setting? Mention trade-offs."
        })

    # 3) HR / behavioral question
    questions.append({
        "id": "behavioral_1",
        "type": "hr",
        "question": "Describe a challenging problem you faced (technical or team), how you diagnosed it, and how you solved it. What did you learn?"
    })

    # 4) Quick problem-solving / critical thinking (use jd keyword if present)
    q_crit_topic = jd_keywords[0] if jd_keywords else (resume_keywords[0] if resume_keywords else "a technical problem")
    questions.append({
        "id": "critical_1",
        "type": "critical",
        "question": f"Quick problem-solving: Suppose you must deliver a minimal viable solution for {q_crit_topic} under tight time and resource constraints. Outline your approach, prioritization, and what you'd ship first."
    })

    # 5) Warmup/ending questions (wrapups)
    questions.append({
        "id": "warmup_1",
        "type": "warmup",
        "question": "Is there anything else you'd like to highlight about your experience that we haven't covered?"
    })
    questions.append({
        "id": "wrapup_1",
        "type": "wrapup",
        "question": "Before we finish, do you have any questions for us about the role or team?"
    })

    plan = {
        "session_id": session_id,
        "candidate": parsed.get("name", "Candidate"),
        "job_role": job_role,
        "summary": parsed.get("summary", ""),
        "total_questions": len(questions),
        "questions": questions
    }

    out_file = sdir / "interview_plan.json"
    _write_json(out_file, plan)
    return {"status": "ok", "total_questions": len(questions), "plan_path": str(out_file)}
