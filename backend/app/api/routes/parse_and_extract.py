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
EMAIL_RE = re.compile(r"[a-zA-Z0-9.+_-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")
PHONE_RE = re.compile(r"(?:\+?\d{1,3}[\s\-.]?)?\(?\d{2,4}\)?[\s\-.]?\d{3,5}[\s\-.]?\d{3,5}")
YEAR_RE = re.compile(r"\b((?:19|20)\d{2})\b")

EDU_KEYWORDS = [
    "bachelor",
    "master",
    "b.sc",
    "m.sc",
    "b.tech",
    "m.tech",
    "b.e",
    "m.e",
    "bs",
    "ms",
    "ba",
    "ma",
    "phd",
    "ph.d",
    "mba",
    "degree",
    "diploma",
    "b.com",
    "bca",
    "mca",
    "b.eng",
    "m.eng",
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
    senior_keywords = [
        "senior",
        "lead",
        "principal",
        "architect",
        "manager",
        "8+ years",
        "10+ years",
    ]
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


def _extract_project_name(project_text: str) -> str:
    """Extract a clean project name from project text using multiple heuristics."""
    lines = [l.strip() for l in project_text.split("\n") if l.strip()]
    if not lines:
        return ""

    # Priority 1: Look for text in quotes (often project names)
    for line in lines[:3]:
        match = re.search(r'["\']([^"\']+)["\']', line)
        if match:
            name = match.group(1).strip()
            if 3 < len(name) < 60 and not any(
                kw in name.lower() for kw in ["bachelor", "master", "degree", "university"]
            ):
                return name

    # Priority 2: First line that looks like a project name
    for line in lines[:3]:
        clean = re.sub(r"^[•\-\*#\s▪>◦▸▹]+", "", line).strip()
        # Skip if contains education keywords
        if any(
            kw in clean.lower()
            for kw in ["bachelor", "master", "degree", "university", "college", "cgpa", "gpa"]
        ):
            continue
        # Skip if it's a clear description starter
        if clean.lower().startswith(
            ("developed", "implemented", "created", "built", "using", "with")
        ):
            continue

        # Check if it looks like a project name
        words = clean.split()
        clean_lower = clean.lower()

        # Tech keywords that indicate project names (including AI/ML terms)
        tech_terms = [
            "app",
            "api",
            "web",
            "system",
            "platform",
            "tool",
            "bot",
            "dashboard",
            "analytics",
            "ml",
            "ai",
            "e-commerce",
            "ecommerce",
            "website",
            "portal",
            "multimodal",
            "simulator",
            "interview",
            "generator",
            "classifier",
            "detector",
            "recognition",
            "chatbot",
            "assistant",
            "recommender",
            "prediction",
            "forecasting",
            "optimization",
            "automation",
            "scraper",
            "crawler",
            "parser",
            "converter",
            "translator",
            "tracker",
            "manager",
            "scheduler",
            "calculator",
            "visualizer",
        ]
        has_tech_term = any(term in clean_lower for term in tech_terms)

        # GitHub-style repo names (kebab-case or snake_case)
        has_repo_style = "-" in clean or "_" in clean

        # Has at least one capitalized word (traditional title)
        cap_words = [w for w in words if w and w[0].isupper() and w.isalpha()]

        # Accept if reasonable length and has some project-like quality
        if 3 < len(clean) < 60:
            # Accept tech-heavy names even if lowercase
            if has_tech_term or has_repo_style or len(cap_words) >= 1:
                return clean
            # Accept short descriptive names (2-5 words, no obvious action verbs)
            if 2 <= len(words) <= 6:
                action_verbs = [
                    "developed",
                    "implemented",
                    "created",
                    "built",
                    "designed",
                    "worked",
                    "made",
                    "using",
                    "with",
                    "and",
                    "the",
                    "for",
                ]
                if not any(words[0].lower().startswith(v) for v in action_verbs):
                    return clean

    # Priority 3: First reasonable line that's not a clear description
    for line in lines[:2]:
        clean = re.sub(r"^[•\-\*#\s▪>◦▸▹]+", "", line).strip()
        clean = re.sub(r"\s+", " ", clean)
        clean_lower = clean.lower()

        # Skip education keywords
        if any(
            kw in clean_lower for kw in ["bachelor", "master", "degree", "university", "college"]
        ):
            continue
        # Skip clear action starters
        if clean_lower.startswith(
            (
                "developed",
                "implemented",
                "created",
                "built",
                "designed",
                "using",
                "with",
                "and",
                "the",
            )
        ):
            continue

        if 3 < len(clean) < 60:
            return clean

    # Fallback: use first line with length limit
    clean = re.sub(r"^[•\-\*#\s▪>◦▸▹]+", "", lines[0]).strip()
    if len(clean) > 60:
        clean = clean[:57] + "..."
    return clean if len(clean) > 3 else ""


def _format_projects_for_display(projects: List[Dict]) -> Dict:
    """
    Format projects with better names for UI display.
    Input: List of dicts with 'name', 'tech_stack', 'details', 'confidence'
    Returns structured dict with count, confidence info, and list of projects.
    """
    formatted_projects = []
    total_confidence = 0.0
    low_confidence_count = 0

    for i, proj in enumerate(projects[:6]):  # Top 6 projects
        # Get name from the structured data
        name = proj.get("name", "").strip()
        tech_stack = proj.get("tech_stack", "").strip()
        details = proj.get("details", "").strip()
        confidence = proj.get("confidence", 0.0)
        extraction_method = proj.get("extraction_method", "unknown")

        # Track confidence stats
        total_confidence += confidence
        if confidence < 0.5:
            low_confidence_count += 1

        # If no name or too short, try to extract better
        if not name or len(name) < 3:
            name = _extract_project_name(details) if details else f"Project {i+1}"

        # Build description with tech stack + details
        description_parts = []
        if tech_stack:
            description_parts.append(f"Tech: {tech_stack}")
        if details:
            description_parts.append(details)

        description = "\n".join(description_parts) if description_parts else "No details available"

        formatted_projects.append(
            {
                "name": name if len(name) > 3 else f"Project {i+1}",
                "tech_stack": tech_stack,
                "description": description[:500],
                "confidence": round(confidence, 2),
                "extraction_method": extraction_method,
            }
        )

    # Calculate overall extraction quality
    avg_confidence = total_confidence / len(projects) if projects else 0.0

    # Quality indicator
    if avg_confidence >= 0.7:
        quality = "high"
    elif avg_confidence >= 0.4:
        quality = "medium"
    else:
        quality = "low"

    return {
        "total_projects_found": len(projects),
        "projects_extracted": len(formatted_projects),
        "average_confidence": round(avg_confidence, 2),
        "extraction_quality": quality,
        "low_confidence_warnings": low_confidence_count,
        "projects": formatted_projects,
    }


def _extract_top_skills(skills: List[str], n: int = 10) -> List[str]:
    """Return top N skills, prioritizing technical ones by category."""
    # Tier 1: Most in-demand programming languages and frameworks
    tier1 = [
        "python",
        "javascript",
        "typescript",
        "java",
        "go",
        "golang",
        "rust",
        "react",
        "react.js",
        "nextjs",
        "angular",
        "vue",
        "vue.js",
        "nodejs",
        "node.js",
        "fastapi",
        "flask",
        "django",
        "spring",
        "spring boot",
        "postgresql",
        "mysql",
        "mongodb",
        "redis",
        "sql",
    ]
    # Tier 2: Cloud, DevOps, and ML/AI
    tier2 = [
        "aws",
        "gcp",
        "azure",
        "docker",
        "kubernetes",
        "terraform",
        "github actions",
        "ci/cd",
        "jenkins",
        "linux",
        "pytorch",
        "tensorflow",
        "machine learning",
        "deep learning",
        "git",
        "github",
        "gitlab",
    ]
    # Tier 3: Other technical skills
    tier3 = [
        "html",
        "html5",
        "css",
        "css3",
        "tailwind",
        "bootstrap",
        "graphql",
        "rest api",
        "websocket",
        "microservices",
        "kafka",
        "spark",
        "airflow",
        "elasticsearch",
        "android",
        "ios",
        "react native",
        "flutter",
    ]

    priority_map = {s: (0, i) for i, s in enumerate(tier1)}
    priority_map.update({s: (1, i) for i, s in enumerate(tier2)})
    priority_map.update({s: (2, i) for i, s in enumerate(tier3)})

    def skill_priority(s):
        s_lower = s.lower()
        return priority_map.get(s_lower, (3, 0))

    sorted_skills = sorted(skills, key=skill_priority)
    return sorted_skills[:n]


@router.post("/parse-and-extract")
async def parse_and_extract_resume(
    session_id: str = Form(...), 
    resume: UploadFile = File(...),
    background: bool = Form(False)
):
    """
    Main endpoint for resume parse and extract. Supports background processing.
    """
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

    if background:
        try:
            from backend.app.worker import app as celery_app
            task = celery_app.send_task("parse_and_extract_resume", args=[session_id, str(file_path), resume.filename])
            return {"status": "accepted", "task_id": task.id, "message": "Resume parsing started in background"}
        except Exception as e:
            import logging
            logging.error(f"⚠️ Celery task failed to enqueue: {e}. Falling back to sync mode.")
            # Fall through to sync mode

    return await parse_and_extract_logic(session_id, file_path, resume.filename)


async def parse_and_extract_logic(session_id: str, file_path: Path, filename: str):
    """
    Core logic for parsing and extracting resume data.
    """
    from backend.app.api.routes.parse_resume import (
        build_parsed_schema,
        _extract_page_text_column_aware,
    )

    try:
        sdir = _storage_dir() / session_id
        
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
                detail="Could not extract text from resume. File may be image-based or corrupted.",
            )

        # Parse the resume
        parsed = build_parsed_schema(filename, raw_text)

        if "error" in parsed:
            raise HTTPException(status_code=422, detail=parsed["error"])

        # Extract additional fields for autofill
        name = parsed.get("name") or _extract_name_from_text(raw_text)
        exp_years = _extract_experience_years(raw_text)
        expertise = _infer_expertise_level(raw_text, exp_years)
        latest_role = _extract_latest_role(raw_text)
        edu_summary = _extract_education_summary(parsed.get("education", []))

        # Save parsed data for later use
        parsed.update(
            {
                "experience_years": exp_years,
                "inferred_expertise": expertise,
                "latest_role": latest_role,
            }
        )

        out_file = sdir / "parsed_resume.json"
        out_file.write_text(json.dumps(parsed, indent=2, ensure_ascii=False), encoding="utf-8")

        # Format projects for UI
        projects_data = _format_projects_for_display(parsed.get("projects", []))

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
                "projects": projects_data.get("projects", []),
                "projects_meta": {
                    "total_found": projects_data.get("total_projects_found", 0),
                    "extraction_quality": projects_data.get("extraction_quality", "unknown"),
                    "average_confidence": projects_data.get("average_confidence", 0),
                },
                "education_summary": edu_summary,
                "experience_years": exp_years,
                "expertise_level": expertise,
                "latest_role": latest_role,
            },
            "raw_excerpt": raw_text[:1000],
            "session_id": session_id,
        }
    except Exception as e:
        import logging
        logging.exception(f"Error in parse_and_extract_logic for session {session_id}: {e}")
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(
            status_code=500, detail=f"Resume parsing failed: {str(e)}"
        )
