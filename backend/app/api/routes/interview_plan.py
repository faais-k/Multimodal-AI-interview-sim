"""
Dynamic interview plan generation.

FIXES in this version:
- Company removed from technical questions (company = target, not employer)  
- Project name hardened against generic phrases ("Full Stack" etc.)
- Question templates varied by expertise level
- Skill selection shuffled for session variety
- Difficulty calibrated: fresher→concepts, senior→architecture+trade-offs
"""
import asyncio
import json
import random
import re
import uuid
from pathlib import Path
from typing import Dict, List, Tuple

from fastapi import APIRouter, HTTPException
from backend.app.core.validation import validate_session_id

router = APIRouter()

EXPERTISE_MAX_FOLLOWUPS = {"fresher": 3, "intermediate": 5, "experienced": 7}
EXPERTISE_TECH_COUNT    = {"fresher": 2, "intermediate": 3, "experienced": 5}

STOPWORDS = {
    "the","and","for","with","that","this","from","your","you","are","will","have",
    "has","use","using","a","an","in","on","to","of","is","it","as","by","be","or",
    "at","we","our","can","not","all","any","but","was","had","also","more","into",
    "than","then","when","where","which","who","were","they","their","its","about",
    "after","before","such","each","very",
}

_GENERIC_NAMES = {
    "full stack","full-stack","fullstack","web development","web dev",
    "backend","frontend","mobile app","mobile application","api","rest api",
    "web app","web application","website","app","application","platform",
    "system","project","software","tool","service","microservice",
    "database","dashboard","portal","admin","client","server",
    "machine learning","ml","ai","deep learning","data science",
    "internship","training","bootcamp","course","certification",
}


def _storage_dir() -> Path:
    from backend.app.core.storage import get_storage_dir
    return get_storage_dir()


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
    out, seen = [], set()
    for s in skills or []:
        s = str(s).strip()
        if s and s.lower() not in seen:
            seen.add(s.lower())
            out.append(s)
    return out


def _project_info(raw_project: str, fallback_idx: int) -> Tuple[str, List[str]]:
    text = (raw_project or "").strip()
    if not text:
        return (f"Project {fallback_idx}", [])

    parts = [p.strip() for p in re.split(r"[-|:–—]", text, maxsplit=1)]
    candidate = parts[0] if parts and parts[0] else ""

    is_generic = (
        candidate.lower().strip() in _GENERIC_NAMES
        or len(candidate.split()) > 6
        or len(candidate) < 3
    )

    if is_generic:
        m = re.search(r"\b([A-Z][a-zA-Z]+(?:\s[A-Z][a-zA-Z]+){0,2})\b", text)
        if m and m.group(1).lower() not in _GENERIC_NAMES and len(m.group(1)) > 3:
            candidate = m.group(1)
        else:
            candidate = " ".join(text.split()[:4]).rstrip(".,;:")

    candidate = candidate.lstrip("•-*# ").strip() or f"Project {fallback_idx}"

    stack = re.findall(
        r"\b(Python|FastAPI|Angular|React|Next\.?js|Node\.?js|TypeScript|JavaScript|"
        r"MongoDB|PostgreSQL|MySQL|SQL|Docker|AWS|Azure|GCP|Flask|Django|Spring|"
        r"TensorFlow|PyTorch|Keras|scikit-learn|Redis|GraphQL|Kubernetes|Terraform)\b",
        text, re.IGNORECASE
    )
    stack = list(dict.fromkeys(stack))
    return (candidate[:60], stack)


_PROJ_EDU_KW = {
    "b.sc","b.tech","m.sc","m.tech","b.e","m.e","mba","bca","mca","b.com","b.eng",
    "m.eng","bachelor","master","diploma","ph.d","phd","university","college",
    "certification","course","bootcamp","nsdc",
}
_PROJ_DATE_RE   = re.compile(r"\b(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)\s+20", re.IGNORECASE)
_PROJ_VERB_RE   = re.compile(r"\b(?:technologies|built|developed|implemented|created|designed|deployed)\b", re.IGNORECASE)


def _filter_valid_projects(projects: List[str]) -> List[str]:
    valid = []
    for p in projects:
        t = str(p).strip()
        if len(t) < 15: continue
        if any(kw in t.lower() for kw in _PROJ_EDU_KW): continue
        if re.match(r"^[•\-\*]\s*(?:b\.sc|b\.tech|m\.sc|m\.tech|b\.e|m\.e|mba|bachelor|master)", t.lower()): continue
        if _PROJ_DATE_RE.search(t) and not _PROJ_VERB_RE.search(t): continue
        valid.append(t)
    return valid


def _pick_skills(resume_skills, role_text, jd_text, count):
    rs = _normalize_skills(resume_skills)
    if not rs: return []
    jd_l = (jd_text or "").lower()
    matched = [s for s in rs if s.lower() in jd_l]
    if matched:
        random.shuffle(matched)
        return matched[:count]
    role_tokens = set(_extract_keywords(role_text or "", top_k=12))
    scored = sorted(rs, key=lambda s: (len(set(_extract_keywords(s.lower(), 4)) & role_tokens) + random.uniform(0, 0.3)), reverse=True)
    return scored[:count] or rs[:count]


# ── Question builders ────────────────────────────────────────────────────────

def _intro(name, role):
    role = role or "this role"
    return random.choice([
        f"Hi {name}, tell me about yourself and what draws you to {role} specifically.",
        f"Welcome {name}! Walk me through your background and why you're pursuing {role}.",
        f"Hi {name}! Please introduce yourself — your key skills and what excites you about {role}.",
    ])


def _project_q(name, stack, role, level):
    stk = f" using {', '.join(stack)}" if stack else ""
    r   = f" relevant to {role}" if role else ""
    if level == "fresher":
        return random.choice([
            f"Tell me about {name}{stk}. What was your role, what problem did it solve, and what did you learn?",
            f"Walk me through {name}{stk}. What was the biggest challenge and how did you overcome it?",
            f"Describe {name}{stk}. What were you personally responsible for, and what would you improve now?",
        ])
    elif level == "intermediate":
        return random.choice([
            f"Tell me about {name}{stk}. What was the most technically challenging part{r}, and how did you approach it?",
            f"Walk me through a key technical decision you made in {name}{stk}. What options did you evaluate?",
            f"In {name}{stk}, what was the hardest design decision you faced{r}?",
        ])
    else:
        return random.choice([
            f"Walk me through the most technically challenging part of {name}{stk} — including trade-offs and measurable outcomes.",
            f"In {name}{stk}, describe a design decision you'd revisit today and why.",
            f"Tell me about a performance or scalability challenge in {name}{stk} and how you resolved it.",
        ])


def _technical_q(skill, role, level):
    """No company context — company is target, not current employer."""
    r = f" for a {role}" if role else ""
    if level == "fresher":
        return random.choice([
            f"Can you explain the core concepts behind {skill} and where you've applied it?",
            f"What do you understand about {skill}? Walk me through how you've used or learned it.",
            f"How would you explain {skill} to someone new? Include a real example from your experience.",
        ])
    elif level == "intermediate":
        return random.choice([
            f"You've listed {skill} as a key skill. Describe a specific problem you solved using it{r}.",
            f"Walk me through a meaningful task where {skill} was central to your solution{r}.",
            f"What are the most important considerations when working with {skill}{r}? Give a concrete example.",
        ])
    else:
        return random.choice([
            f"You've worked with {skill} extensively. Describe a production-level architectural decision involving {skill}{r}, including trade-offs and outcomes.",
            f"Tell me about the most complex problem you've solved using {skill}{r}. What alternatives did you reject?",
            f"How have you optimised or scaled a system built with {skill}{r}? Walk me through specific bottlenecks.",
        ])


def _behavioral_q(level):
    if level == "fresher":
        return random.choice([
            "Tell me about a time you had to learn something new quickly for a project. How did you approach it?",
            "Describe a situation where you collaborated with someone with a different working style. How did you handle it?",
            "Tell me about a time a project didn't go as planned. What happened and what did you learn?",
        ])
    elif level == "intermediate":
        return random.choice([
            "Tell me about a time you had to adapt your communication style to work with a very different colleague on a technical task.",
            "Describe a situation where you disagreed with a technical decision your team made. How did you handle it?",
            "Tell me about a time you had to balance competing priorities under a tight deadline.",
        ])
    else:
        return random.choice([
            "Tell me about a time you had to influence a technical decision without direct authority. How did you build consensus?",
            "Describe a situation where you had to mentor a junior team member through a difficult technical problem.",
            "Tell me about a high-stakes technical decision you made with incomplete information. What was your process?",
        ])


def _critical_q(skill, role, level):
    role_txt = role or "software engineer"
    if level == "fresher":
        return random.choice([
            f"An application built with {skill} is taking 10 seconds to load. How would you start investigating?",
            f"A bug is reported — users can't log in to a {skill} app. Walk me through your debugging process.",
            f"If you were deploying a small {skill} app to production for the first time, what steps would you take?",
        ])
    elif level == "intermediate":
        return random.choice([
            f"A feature using {skill} is causing slow response times in staging. Walk me through how you'd diagnose and fix it.",
            f"You inherit a {skill} codebase with no documentation and a critical production bug. What's your approach?",
            f"A {skill} service starts failing intermittently under load. How do you investigate and fix it?",
        ])
    else:
        return random.choice([
            f"You are the on-call {role_txt}. A {skill}-based service is causing cascading failures in production. Walk me through your response.",
            f"Your {skill} system needs to scale 10× in 3 months due to unexpected growth. What's your architectural approach?",
            f"A security vulnerability is discovered in a core {skill} dependency in production. How do you respond?",
        ])


def _wrapup_q(company):
    if company:
        return random.choice([
            f"Before we wrap up, what questions do you have about the role and engineering culture at {company}?",
            f"We're almost done — is there anything about the team or technical environment at {company} you'd like to know?",
        ])
    return random.choice([
        "Before we wrap up, what questions do you have for us about the role and team?",
        "We're almost done — is there anything you'd like to share or ask about this position?",
    ])


def _pregenerate_followups(questions: list, job_role: str, expertise_level: str) -> dict:
    try:
        from backend.app.core.ml_models import get_llm_model, llm_generate, load_llm_model
        model, _ = get_llm_model()
        if model is None:
            model, _ = load_llm_model()
        if model is None:
            return {}
        cached = {}
        for q in questions:
            if q.get("type") not in ("technical", "project", "critical"):
                continue
            skill = q.get("skill_target", "")
            q_text = q.get("question", "")
            style = (
                "Ask for a specific example from their coursework or personal projects." if expertise_level == "fresher"
                else "Ask about a concrete challenge they faced and how they resolved it." if expertise_level == "intermediate"
                else "Ask about the trade-offs they considered and measurable impact."
            )
            prompt = f"""Generate ONE short follow-up question for a technical interview.
Topic: {skill}
Original question: {q_text}
Role: {job_role or 'software engineer'}
Level: {expertise_level}
The follow-up should: {style}
Be under 100 characters. Start directly (no preamble). Don't repeat the original.
Respond with ONLY the question."""
            fq = llm_generate(prompt, max_new_tokens=60, temperature=0.0).strip().strip("\"'")
            if fq and 10 < len(fq) < 120:
                if not fq.endswith("?"): fq += "?"
                cached[q["id"]] = fq
        return cached
    except Exception:
        return {}


@router.post("/interview/plan/{session_id}")
async def create_interview_plan(session_id: str):
    validate_session_id(session_id)
    sdir = _storage_dir() / session_id
    if not sdir.exists():
        raise HTTPException(status_code=404, detail="Session not found.")

    parsed_p = sdir / "parsed_resume.json"
    if not parsed_p.exists():
        raise HTTPException(status_code=404, detail="Parsed resume not found. Run /parse/resume first.")
    parsed = _read_json(parsed_p)

    jd   = _read_json(sdir / "job_description.json")   if (sdir / "job_description.json").exists()   else {}
    prof = _read_json(sdir / "candidate_profile.json") if (sdir / "candidate_profile.json").exists() else {}

    candidate_name   = parsed.get("name") or prof.get("name") or "Candidate"
    resume_skills    = _normalize_skills(parsed.get("skills", []))
    resume_projects  = _filter_valid_projects(parsed.get("projects", []) or [])
    education        = parsed.get("education", [])
    job_role         = (prof.get("job_role") or jd.get("job_role") or "").strip()
    expertise_level  = (prof.get("expertise_level") or "fresher").lower()
    if expertise_level not in EXPERTISE_MAX_FOLLOWUPS:
        expertise_level = "fresher"
    experience_summary = (prof.get("experience_summary") or prof.get("experience") or "").strip()
    job_description  = (jd.get("job_description") or "").strip()
    company          = (jd.get("company") or "").strip()

    target_skills = _pick_skills(resume_skills, job_role, job_description or job_role, EXPERTISE_TECH_COUNT[expertise_level])

    questions: List[Dict] = []

    questions.append({"id":"intro_1","type":"self_intro","question":_intro(candidate_name,job_role),"skill_target":"self_intro","source":"rule"})

    if resume_projects:
        p1, s1 = _project_info(str(resume_projects[0]), 1)
        questions.append({"id":"project_1","type":"project","question":_project_q(p1,s1,job_role,expertise_level),"skill_target":p1,"source":"rule"})
        if len(resume_projects) > 1:
            p2, s2 = _project_info(str(resume_projects[1]), 2)
            questions.append({"id":str(uuid.uuid4()),"type":"project","question":_project_q(p2,s2,job_role,expertise_level),"skill_target":p2,"source":"rule"})
    else:
        questions.append({"id":"project_1","type":"project","question":random.choice(["Walk me through the most technically challenging thing you've built and your exact contribution.","Tell me about a significant technical challenge you tackled — from coursework, open source, or self-learning."]),"skill_target":"project_experience","source":"rule"})

    for skill in target_skills:
        questions.append({"id":str(uuid.uuid4()),"type":"technical","question":_technical_q(skill,job_role,expertise_level),"skill_target":skill,"source":"rule"})

    questions.append({"id":"behavioral_1","type":"hr","question":_behavioral_q(expertise_level),"skill_target":"collaboration","source":"rule"})

    scenario = target_skills[0] if target_skills else (resume_skills[0] if resume_skills else "your tech stack")
    questions.append({"id":"critical_1","type":"critical","question":_critical_q(scenario,job_role,expertise_level),"skill_target":scenario,"source":"rule"})

    questions.append({"id":"wrapup_1","type":"wrapup","question":_wrapup_q(company),"skill_target":company or "wrapup","source":"rule"})

    try:
        followup_cache = await asyncio.wait_for(asyncio.to_thread(_pregenerate_followups,questions,job_role,expertise_level),timeout=90.0)
    except asyncio.TimeoutError:
        print("⚠️  followup pre-generation timed out")
        followup_cache = {}

    plan = {
        "session_id":session_id,"candidate":candidate_name,"job_role":job_role,
        "company":company,"expertise_level":expertise_level,"experience_summary":experience_summary,
        "education":education,"summary":parsed.get("summary",""),"total_questions":len(questions),
        "used_llm":False,"max_followups":EXPERTISE_MAX_FOLLOWUPS[expertise_level],
        "questions":questions,"followup_cache":followup_cache,
    }
    _write_json(sdir / "interview_plan.json", plan)

    return {"status":"ok","total_questions":len(questions),"expertise_level":expertise_level,"company":company,"used_llm":False}
