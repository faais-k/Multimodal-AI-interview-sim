"""
Dynamic interview plan generation from candidate/job context.

P3-A: _pregenerate_followups() runs at plan-creation time to warm up a cache
of depth-1 follow-up questions for technical/project/critical questions.
This eliminates LLM latency from the live interview loop for depth-1 follow-ups.
"""
import asyncio
import json
import re
import uuid
from pathlib import Path
from typing import Dict, List, Tuple

from fastapi import APIRouter, HTTPException

router = APIRouter()

EXPERTISE_MAX_FOLLOWUPS = {
    "fresher": 3,
    "intermediate": 5,
    "experienced": 7,
}
EXPERTISE_TECH_COUNT = {
    "fresher": 3,
    "intermediate": 4,
    "experienced": 5,
}
STOPWORDS = {
    "the", "and", "for", "with", "that", "this", "from", "your", "you", "are",
    "will", "have", "has", "use", "using", "a", "an", "in", "on", "to", "of",
    "is", "it", "as", "by", "be", "or", "at", "we", "our", "can", "not", "all",
    "any", "but", "was", "had", "also", "more", "into", "than", "then", "when",
    "where", "which", "who", "were", "they", "their", "its", "about", "after",
    "before", "such", "each", "very",
}


def _storage_dir() -> Path:
    return Path(__file__).resolve().parents[4] / "storage"


def _read_json(p: Path) -> dict:
    return json.loads(p.read_text(encoding="utf-8"))


def _write_json(p: Path, data: dict):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data, indent=2), encoding="utf-8")


def _extract_keywords(text: str, top_k: int = 12) -> List[str]:
    if not text:
        return []
    tokens = re.findall(r"[a-zA-Z0-9\-\_]{3,}", text.lower())
    tokens = [t for t in tokens if t not in STOPWORDS and not t.isdigit()]
    freq: Dict[str, int] = {}
    for t in tokens:
        freq[t] = freq.get(t, 0) + 1
    return [k for k, _ in sorted(freq.items(), key=lambda x: x[1], reverse=True)[:top_k]]


def _normalize_skills(skills: List[str]) -> List[str]:
    out: List[str] = []
    seen = set()
    for s in skills or []:
        s = str(s).strip()
        if not s:
            continue
        k = s.lower()
        if k not in seen:
            seen.add(k)
            out.append(s)
    return out


def _project_info(raw_project: str, fallback_idx: int) -> Tuple[str, List[str]]:
    text = (raw_project or "").strip()
    if not text:
        return (f"Project {fallback_idx}", [])
    parts = [p.strip() for p in re.split(r"[-|:]", text, maxsplit=1)]
    name = parts[0] if parts and parts[0] else f"Project {fallback_idx}"
    stack = re.findall(r"\b(Python|FastAPI|Angular|React|Node\.?js|TypeScript|JavaScript|MongoDB|PostgreSQL|SQL|Docker|AWS|Azure|GCP)\b", text, re.IGNORECASE)
    stack = list(dict.fromkeys([s if isinstance(s, str) else str(s) for s in stack]))
    return (name, stack)


_PROJ_EDU_KEYWORDS = {
    "b.sc", "b.tech", "m.sc", "m.tech", "b.e", "m.e", "mba", "bca", "mca",
    "b.com", "b.eng", "m.eng", "bachelor", "master", "diploma", "ph.d", "phd",
    "university", "college", "certification", "course", "bootcamp", "nsdc",
}
_PROJ_DATE_RE = re.compile(r"\b(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)\s+20", re.IGNORECASE)
_PROJ_VALID_VERBS = re.compile(r"\b(?:technologies|built|developed|implemented|created|designed|deployed)\b", re.IGNORECASE)


def _filter_valid_projects(projects: List[str]) -> List[str]:
    """Remove entries that are actually education, certifications, or noise.

    Prevents two-column PDF artifacts (e.g. an education line appearing as
    a project) from being used as interview question topics.
    """
    valid: List[str] = []
    for p in projects:
        text = str(p).strip()
        lower = text.lower()

        # Too short to be a real project description
        if len(text) < 15:
            continue

        # Contains education keywords
        if any(kw in lower for kw in _PROJ_EDU_KEYWORDS):
            continue

        # Starts with bullet + degree keyword  (e.g. "• B.Sc. Computer Science")
        if re.match(r"^[•\-\*]\s*(?:b\.sc|b\.tech|m\.sc|m\.tech|b\.e|m\.e|mba|bachelor|master)", lower):
            continue

        # Date-only entry (contains "Sep 20.." etc.) without project verbs
        if _PROJ_DATE_RE.search(text) and not _PROJ_VALID_VERBS.search(text):
            continue

        valid.append(text)

    if not valid and projects:
        import logging
        logging.warning("No valid projects found after filtering — skipping project stage")

    return valid


def _pick_target_skills(resume_skills: List[str], role_text: str, jd_text: str, count: int) -> List[str]:
    rs = _normalize_skills(resume_skills)
    if not rs:
        return []
    jd_l = (jd_text or "").lower()
    role_l = (role_text or "").lower()

    both = [s for s in rs if s.lower() in jd_l]
    if both:
        return both[:count]

    role_tokens = set(_extract_keywords(role_l, top_k=12))
    scored = []
    for s in rs:
        s_tokens = set(_extract_keywords(s.lower(), top_k=4))
        overlap = len(s_tokens & role_tokens)
        scored.append((overlap, s))
    scored.sort(key=lambda x: x[0], reverse=True)
    picked = [s for _, s in scored if s][:count]
    return picked if picked else rs[:count]


def _build_intro_question(name: str, job_role: str) -> str:
    role = job_role or "this role"
    return f"Hi {name}, tell me about yourself and what draws you to {role} specifically."


def _build_project_question(project_name: str, stack: List[str], role: str) -> str:
    stack_txt = f" using {', '.join(stack)}" if stack else ""
    role_txt = f" for a {role} context" if role else ""
    return (
        f"I see you built {project_name}{stack_txt}. "
        f"Walk me through the most technically challenging part of that project{role_txt}."
    )


def _build_technical_question(skill: str, role: str, company: str) -> str:
    company_ctx = f" at {company}" if company else ""
    role_ctx = f" for a {role}" if role else ""
    return (
        f"You've listed {skill} as a key skill. "
        f"Explain a production-level decision you made while using {skill}{role_ctx}{company_ctx}, "
        "including trade-offs and the outcome."
    )


def _build_behavioral_question(company: str) -> str:
    if company:
        return (
            f"{company} values collaboration across teams. "
            "Tell me about a time you had to adapt your communication style to work effectively with a very different colleague."
        )
    return (
        "Tell me about a time you had to adapt your communication style to work effectively with a very different colleague on a technical task."
    )


def _build_critical_question(stack_or_skill: str, role: str) -> str:
    role_txt = role or "full stack engineer"
    return (
        f"You are the on-call {role_txt}. A production feature built with {stack_or_skill} is causing slow page loads and timeout errors. "
        "Walk me through how you would diagnose the issue, prioritize fixes, and validate improvement."
    )


def _build_wrapup_question(company: str) -> str:
    if company:
        return f"Before we wrap up, what questions do you have for us about the role and engineering culture at {company}?"
    return "Before we wrap up, what questions do you have for us about the role and team?"


def _pregenerate_followups(questions: list, job_role: str) -> dict:
    """Pre-generate one depth-1 follow-up per technical/project/critical question.

    Runs synchronously during plan generation (before the interview starts).
    Returns a dict {question_id: follow_up_text} written into plan["followup_cache"].
    Returns {} silently if LLM is unavailable — interview proceeds normally.

    Only generates for types: technical, project, critical.
    Skips intro, behavioral, wrapup (follow-ups there are not useful).
    """
    try:
        from backend.app.core.ml_models import get_llm_model, llm_generate

        model, _ = get_llm_model()
        if model is None:
            return {}

        cached: dict = {}
        for q in questions:
            qtype = q.get("type", "")
            if qtype not in ("technical", "project", "critical"):
                continue  # Only pre-generate for substantive question types

            skill         = q.get("skill_target", "")
            question_text = q.get("question", "")

            prompt = f"""Generate ONE short follow-up question for a technical interview.
Topic: {skill}
Original question: {question_text}
Role: {job_role or 'software engineer'}

The follow-up should:
- Ask for a concrete real-world example
- Be under 100 characters
- Start directly (no preamble like "Great!" or "Good answer")

Respond with ONLY the question."""

            q_text = llm_generate(prompt, max_new_tokens=60, temperature=0.0).strip()
            q_text = q_text.strip("\"'")
            if q_text and 10 < len(q_text) < 120:
                if not q_text.endswith("?"):
                    q_text += "?"
                cached[q["id"]] = q_text

        return cached

    except Exception:
        return {}


@router.post("/interview/plan/{session_id}")
async def create_interview_plan(session_id: str):
    sdir = _storage_dir() / session_id
    if not sdir.exists():
        raise HTTPException(status_code=404, detail="Session not found.")

    parsed_p = sdir / "parsed_resume.json"
    if not parsed_p.exists():
        raise HTTPException(status_code=404, detail="Parsed resume not found. Run /parse/resume first.")
    parsed = _read_json(parsed_p)

    jd = _read_json(sdir / "job_description.json") if (sdir / "job_description.json").exists() else {}
    prof = _read_json(sdir / "candidate_profile.json") if (sdir / "candidate_profile.json").exists() else {}

    candidate_name = parsed.get("name") or prof.get("name") or "Candidate"
    resume_skills = _normalize_skills(parsed.get("skills", []))
    resume_projects_raw = parsed.get("projects", []) or []
    resume_projects = _filter_valid_projects(resume_projects_raw)
    education = parsed.get("education", [])

    job_role = (prof.get("job_role") or jd.get("job_role") or "").strip()
    expertise_level = (prof.get("expertise_level") or "fresher").lower()
    if expertise_level not in EXPERTISE_MAX_FOLLOWUPS:
        expertise_level = "fresher"
    experience_summary = (prof.get("experience_summary") or prof.get("experience") or "").strip()
    job_description = (jd.get("job_description") or "").strip()
    company = (jd.get("company") or "").strip()

    tech_count = EXPERTISE_TECH_COUNT[expertise_level]
    target_skills = _pick_target_skills(resume_skills, job_role, job_description or job_role, tech_count)

    questions: List[Dict] = []

    # Structural fixed questions
    questions.append({
        "id": "intro_1",
        "type": "self_intro",
        "question": _build_intro_question(candidate_name, job_role),
        "skill_target": "self_intro",
        "source": "rule",
    })

    if resume_projects:
        p1_name, p1_stack = _project_info(str(resume_projects[0]), 1)
        questions.append({
            "id": "project_1",
            "type": "project",
            "question": _build_project_question(p1_name, p1_stack, job_role),
            "skill_target": p1_name,
            "source": "rule",
        })
        if len(resume_projects) > 1:
            p2_name, p2_stack = _project_info(str(resume_projects[1]), 2)
            questions.append({
                "id": str(uuid.uuid4()),
                "type": "project",
                "question": _build_project_question(p2_name, p2_stack, job_role),
                "skill_target": p2_name,
                "source": "rule",
            })
    else:
        questions.append({
            "id": "project_1",
            "type": "project",
            "question": (
                "You have listed hands-on experience in your resume. "
                "Walk me through the most technically challenging thing you have built and your exact contribution."
            ),
            "skill_target": "project_experience",
            "source": "rule",
        })

    for skill in target_skills:
        questions.append({
            "id": str(uuid.uuid4()),
            "type": "technical",
            "question": _build_technical_question(skill, job_role, company),
            "skill_target": skill,
            "source": "rule",
        })

    questions.append({
        "id": "behavioral_1",
        "type": "hr",
        "question": _build_behavioral_question(company),
        "skill_target": "collaboration",
        "source": "rule",
    })

    scenario_anchor = target_skills[0] if target_skills else (resume_skills[0] if resume_skills else "your core tech stack")
    questions.append({
        "id": "critical_1",
        "type": "critical",
        "question": _build_critical_question(scenario_anchor, job_role),
        "skill_target": scenario_anchor,
        "source": "rule",
    })

    questions.append({
        "id": "wrapup_1",
        "type": "wrapup",
        "question": _build_wrapup_question(company),
        "skill_target": company or "wrapup",
        "source": "rule",
    })

    # P3-A: Pre-generate depth-1 follow-ups for technical/project/critical questions.
    # This runs while the candidate is on the pre-interview screen (before interview starts)
    # so that depth-1 follow-ups can be served from cache with zero LLM latency at runtime.
    # BUG 5 fix: run LLM pre-generation in a thread to avoid blocking the event loop
    try:
        followup_cache = await asyncio.wait_for(
            asyncio.to_thread(_pregenerate_followups, questions, job_role),
            timeout=90.0,
        )
    except asyncio.TimeoutError:
        print("⚠️  followup pre-generation timed out — cache will be empty")
        followup_cache = {}

    plan = {
        "session_id":       session_id,
        "candidate":        candidate_name,
        "job_role":         job_role,
        "company":          company,
        "expertise_level":  expertise_level,
        "experience_summary": experience_summary,
        "education":        education,
        "summary":          parsed.get("summary", ""),
        "total_questions":  len(questions),
        "used_llm":         False,
        "max_followups":    EXPERTISE_MAX_FOLLOWUPS[expertise_level],
        "questions":        questions,
        "followup_cache":   followup_cache,   # P3-A: {question_id: follow_up_text}
    }

    _write_json(sdir / "interview_plan.json", plan)

    return {
        "status": "ok",
        "total_questions": len(questions),
        "expertise_level": expertise_level,
        "company": company,
        "used_llm": False,
    }
