"""
Resume Parse + Extract API — Returns structured data for form autofill.

This endpoint parses the resume and returns extracted fields that can be used
to pre-fill the interview setup form. It combines parsing with intelligent
extraction of name, skills, projects, experience, and education.
"""

import json
import re
from pathlib import Path
from typing import Dict, List, Optional

from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from backend.app.core.validation import validate_session_id

router = APIRouter()

# Reuse patterns from parse_resume.py
EMAIL_RE    = re.compile(r"[a-zA-Z0-9.+_-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")
PHONE_RE    = re.compile(r"(?:\+?\d{1,3}[\s\-.]?)?\(?\d{2,4}\)?[\s\-.]?\d{3,5}[\s\-.]?\d{3,5}")
YEAR_RE     = re.compile(r"\b((?:19|20)\d{2})\b")

EDU_KEYWORDS = [
    "bachelor", "master", "b.sc", "m.sc", "b.tech", "m.tech", "b.e", "m.e",
    "bs", "ms", "ba", "ma", "phd", "ph.d", "mba", "degree", "diploma",
    "b.com", "bca", "mca", "b.eng", "m.eng",
]

def _storage_dir() -> Path:
    from backend.app.core.storage import get_storage_dir
    return get_storage_dir()


def _extract_name_from_text(text: str) -> Optional[str]:
    """Extract candidate name from first 20 lines using heuristics."""
    for line in text.splitlines()[:20]:
        line = line.strip()
        if not line or len(line) > 50:
            continue
        if any(c in line for c in ["@", "http", "www", "|", "+", "©"]):
            continue
        if re.search(r"https?://", line, re.IGNORECASE):
            continue
        if "linkedin.com" in line.lower() or "github.com" in line.lower():
            continue
        if re.search(r"\d{4,}", line):
            continue
        words = line.split()
        cap_words = [w for w in words if w and w[0].isupper() and w.isalpha()]
        if 1 <= len(cap_words) <= 4 and 2 <= len(words) <= 5:
            return " ".join(words[:4])
    return None


def _extract_experience_years(text: str) -> int:
    """Estimate years of experience from work history."""
    years = YEAR_RE.findall(text)
    if len(years) >= 2:
        try:
            year_nums = sorted([int(y) for y in years])
            # Assume most recent year is current/graduation
            span = year_nums[-1] - year_nums[0]
            return min(max(span, 0), 30)  # Cap at 30 years
        except:
            pass
    return 0


def _infer_expertise_level(text: str, exp_years: int) -> str:
    """Infer expertise level from experience years and content."""
    text_lower = text.lower()
    
    # Check for senior keywords
    senior_keywords = ["senior", "lead", "principal", "architect", "manager", "8+ years", "10+ years"]
    if any(kw in text_lower for kw in senior_keywords) or exp_years >= 7:
        return "experienced"
    
    # Check for mid-level keywords
    mid_keywords = ["mid-level", "intermediate", "3+ years", "5+ years", "engineer"]
    if any(kw in text_lower for kw in mid_keywords) or exp_years >= 2:
        return "intermediate"
    
    return "fresher"


def _extract_education_summary(edu_list: List[Dict]) -> str:
    """Create education summary from parsed education entries."""
    if not edu_list:
        return ""
    
    summaries = []
    for edu in edu_list[:2]:  # Top 2 education entries
        keyword = edu.get("keyword", "")
        years = edu.get("years", [])
        year_str = f" ({years[-1]})" if years else ""
        if keyword:
            summaries.append(f"{keyword.upper()}{year_str}")
    
    return ", ".join(summaries)


def _extract_latest_role(text: str) -> str:
    """Extract latest job role from experience section."""
    # Look for common job titles
    role_patterns = [
        r"\b(Software Engineer|Developer|Engineer|Analyst|Manager|Consultant|Intern)\b",
        r"\b(Full Stack|Frontend|Backend|DevOps|Data|ML|AI)\s+(Developer|Engineer)?\b",
    ]
    
    for pattern in role_patterns:
        matches = re.findall(pattern, text, re.IGNORECASE)
        if matches:
            # Return the first match, properly formatted
            match = matches[0]
            if isinstance(match, tuple):
                return " ".join(filter(None, match)).title()
            return match.title()
    
    return ""


def _format_projects_for_display(projects: List[str]) -> List[Dict]:
    """Format projects with better names for UI display."""
    formatted = []
    for i, proj in enumerate(projects[:4]):  # Top 4 projects
        # Try to extract a clean name
        lines = proj.strip().split('\n')
        first_line = lines[0][:80] if lines else f"Project {i+1}"
        
        # Clean up the first line
        name = re.sub(r"^[•\-\*#\s]+", "", first_line)
        if len(name) > 60:
            name = name[:57] + "..."
        
        formatted.append({
            "name": name if len(name) > 5 else f"Project {i+1}",
            "description": proj[:300]
        })
    
    return formatted


def _extract_top_skills(skills: List[str], n: int = 8) -> List[str]:
    """Return top N skills, prioritizing technical ones."""
    priority_skills = [
        "python", "javascript", "typescript", "java", "react", "nodejs", 
        "docker", "aws", "sql", "mongodb", "kubernetes", "git",
        "fastapi", "flask", "django", "angular", "vue", "nextjs"
    ]
    
    # Sort skills by priority
    def skill_priority(s):
        s_lower = s.lower()
        if s_lower in priority_skills:
            return (0, priority_skills.index(s_lower))
        return (1, 0)
    
    sorted_skills = sorted(skills, key=skill_priority)
    return sorted_skills[:n]


@router.post("/parse-and-extract")
async def parse_and_extract_resume(
    session_id: str = Form(...),
    resume: UploadFile = File(...)
):
    """
    Parse uploaded resume and return structured data for form autofill.
    
    Returns:
    - name: Extracted candidate name
    - email: Email address
    - phone: Phone number
    - skills: List of technical skills
    - projects: List of projects with descriptions
    - education_summary: Education summary string
    - experience_years: Estimated years of experience
    - expertise_level: Inferred level (fresher/intermediate/experienced)
    - latest_role: Latest job title if available
    - raw_text_excerpt: First 1000 chars of extracted text for verification
    """
    from backend.app.api.routes.parse_resume import (
        build_parsed_schema, _extract_pdf_text, _extract_page_text_column_aware
    )
    
    validate_session_id(session_id)
    
    # Save uploaded file
    sdir = _storage_dir() / session_id
    sdir.mkdir(parents=True, exist_ok=True)
    
    resume_dir = sdir / "resumes"
    resume_dir.mkdir(exist_ok=True)
    
    safe_filename = Path(resume.filename or "resume").name
    if not safe_filename or safe_filename.startswith("."):
        safe_filename = "resume.pdf"
    file_path = resume_dir / safe_filename
    
    # Stream write with size limit (10 MB) - atomic write pattern
    MAX_SIZE = 10 * 1024 * 1024  # 10 MB
    size = 0
    temp_path = resume_dir / f".tmp_{safe_filename}"
    try:
        with temp_path.open("wb") as f:
            while chunk := await resume.read(64 * 1024):
                size += len(chunk)
                if size > MAX_SIZE:
                    temp_path.unlink(missing_ok=True)
                    raise HTTPException(413, "Resume too large. Max 10 MB.")
                f.write(chunk)
        # Atomic rename
        temp_path.replace(file_path)
    except Exception:
        temp_path.unlink(missing_ok=True)
        raise
    
    # Extract text based on file type
    raw_text = ""
    try:
        if file_path.suffix.lower() == ".pdf":
            import pdfplumber
            with pdfplumber.open(file_path) as pdf:
                pages_text = []
                for page in pdf.pages:
                    t = _extract_page_text_column_aware(page)
                    if t:
                        pages_text.append(t)
                raw_text = "\n".join(pages_text)
        elif file_path.suffix.lower() in (".docx", ".doc"):
            import docx2txt
            raw_text = docx2txt.process(str(file_path))
        else:
            raw_text = file_path.read_text(encoding="utf-8", errors="ignore")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to extract text: {e}")
    
    if not raw_text or not raw_text.strip():
        raise HTTPException(
            status_code=422,
            detail="Could not extract text from resume. File may be image-based or corrupted."
        )
    
    # Parse the resume
    parsed = build_parsed_schema(resume.filename, raw_text)
    
    if "error" in parsed:
        raise HTTPException(status_code=422, detail=parsed["error"])
    
    # Extract additional fields for autofill
    name = parsed.get("name") or _extract_name_from_text(raw_text)
    exp_years = _extract_experience_years(raw_text)
    expertise = _infer_expertise_level(raw_text, exp_years)
    latest_role = _extract_latest_role(raw_text)
    edu_summary = _extract_education_summary(parsed.get("education", []))
    
    # Save parsed data for later use
    parsed.update({
        "experience_years": exp_years,
        "inferred_expertise": expertise,
        "latest_role": latest_role,
    })
    
    out_file = sdir / "parsed_resume.json"
    out_file.write_text(json.dumps(parsed, indent=2, ensure_ascii=False), encoding="utf-8")
    
    # Format projects for UI
    formatted_projects = _format_projects_for_display(parsed.get("projects", []))
    
    # Get top skills
    top_skills = _extract_top_skills(parsed.get("skills", []))
    
    return {
        "status": "ok",
        "extracted": {
            "name": name,
            "email": parsed.get("email"),
            "phone": parsed.get("phones", [None])[0],
            "skills": top_skills,
            "all_skills": parsed.get("skills", []),
            "projects": formatted_projects,
            "education_summary": edu_summary,
            "experience_years": exp_years,
            "expertise_level": expertise,
            "latest_role": latest_role,
        },
        "raw_excerpt": raw_text[:1000],
        "session_id": session_id,
    }
