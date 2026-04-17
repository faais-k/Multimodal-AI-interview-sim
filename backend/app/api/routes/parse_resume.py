"""
Resume Parser — PDF and DOCX text extraction with structured field detection.
"""

import json
import re
from pathlib import Path
from typing import List, Optional

import docx2txt
import pdfplumber
from fastapi import APIRouter, HTTPException

router = APIRouter()


def _storage_dir() -> Path:
    from backend.app.core.storage import get_storage_dir
    return get_storage_dir()

# ── Regexes ───────────────────────────────────────────────────────────────────
EMAIL_RE    = re.compile(r"[a-zA-Z0-9.+_-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")
PHONE_RE    = re.compile(r"(?:\+?\d{1,3}[\s\-.]?)?\(?\d{2,4}\)?[\s\-.]?\d{3,5}[\s\-.]?\d{3,5}")
YEAR_RE     = re.compile(r"\b((?:19|20)\d{2})\b")
URL_RE      = re.compile(r"https?://\S+|www\.\S+")
LINKEDIN_RE = re.compile(r"linkedin\.com/in/[\w\-]+", re.IGNORECASE)
GITHUB_RE   = re.compile(r"github\.com/[\w\-]+",      re.IGNORECASE)

# ── Section header patterns ───────────────────────────────────────────────────
SECTION_PATTERNS = {
    "summary":        re.compile(r"^\s*(summary|objective|profile|about me|career objective)\s*$", re.IGNORECASE),
    "skills":         re.compile(r"^\s*(skills?|technical skills?|core competencies|technologies|tech stack)\s*$", re.IGNORECASE),
    "experience":     re.compile(r"^\s*(experience|work experience|employment|professional experience|internship)\s*$", re.IGNORECASE),
    "education":      re.compile(r"^\s*(education|academic|qualification|degree)\s*$", re.IGNORECASE),
    "projects":       re.compile(r"^\s*(projects?|personal projects?|academic projects?|key projects?)\s*$", re.IGNORECASE),
    "certifications": re.compile(r"^\s*(certifications?|courses?|training|achievements?)\s*$", re.IGNORECASE),
}

EDU_KEYWORDS = [
    "bachelor", "master", "b.sc", "m.sc", "b.tech", "m.tech", "b.e", "m.e",
    "bs", "ms", "ba", "ma", "phd", "ph.d", "mba", "degree", "diploma",
    "b.com", "bca", "mca", "b.eng", "m.eng",
]

PROJECT_KEYWORDS = [
    "project", "built", "developed", "implemented", "created", "designed",
    "worked on", "contributed", "deployed", "architected", "engineered",
]

# ── Skills list ───────────────────────────────────────────────────────────────
# NOTE: single-letter "c" removed — too ambiguous (matches "scientific", etc.)
# Use "c language" or "c programming" instead.
SKILLS_LIST = [
    # Languages
    "python", "java", "javascript", "typescript", "c language", "c programming",
    "c++", "c#", "go", "golang", "rust", "ruby", "php", "swift", "kotlin",
    "scala", "r", "matlab", "perl", "dart", "lua", "haskell", "elixir", "clojure",
    # ML/AI
    "pytorch", "tensorflow", "keras", "scikit-learn", "sklearn",
    "machine learning", "deep learning", "nlp", "natural language processing",
    "computer vision", "reinforcement learning", "transformers", "bert", "gpt",
    "llm", "langchain", "huggingface", "xgboost", "lightgbm", "catboost",
    "pandas", "numpy", "scipy", "matplotlib", "seaborn", "plotly",
    "openai", "stable diffusion", "generative ai",
    # Web
    "react", "vue", "angular", "nextjs", "nuxtjs", "svelte",
    "nodejs", "express", "fastapi", "flask", "django", "spring", "spring boot",
    "laravel", "rails", "asp.net", "graphql", "rest api", "websocket",
    "html", "css", "tailwind", "bootstrap", "sass",
    # Data / DB
    "sql", "mysql", "postgresql", "sqlite", "mongodb", "redis", "cassandra",
    "elasticsearch", "firebase", "dynamodb", "neo4j", "supabase",
    "spark", "hadoop", "kafka", "airflow", "dbt", "snowflake", "bigquery",
    "tableau", "power bi", "looker",
    # DevOps / Cloud
    "docker", "kubernetes", "terraform", "ansible", "jenkins", "github actions",
    "aws", "gcp", "azure", "heroku", "vercel", "netlify",
    "linux", "bash", "shell scripting", "nginx", "apache",
    "ci/cd", "devops", "microservices",
    # Mobile
    "android", "ios", "react native", "flutter", "xamarin",
    # CV
    "opencv", "pillow", "mediapipe", "yolo", "object detection",
    # Tools
    "git", "github", "gitlab", "bitbucket",
    "unity", "unreal", "blender",
    "solidity", "blockchain", "web3",
    "figma", "photoshop", "illustrator",
]


# ── Section splitter ──────────────────────────────────────────────────────────

def split_sections(text: str) -> dict:
    lines    = text.splitlines()
    sections: dict = {
        "_header": [], "summary": [], "skills": [], "experience": [],
        "education": [], "projects": [], "certifications": [], "_other": [],
    }
    current = "_header"
    for line in lines:
        stripped = line.strip()
        matched  = False
        for sec, pat in SECTION_PATTERNS.items():
            if pat.match(stripped):
                current = sec
                matched = True
                break
        if not matched:
            sections.setdefault(current, []).append(line)
    return sections


# ── Extractors ────────────────────────────────────────────────────────────────

def extract_name(text: str) -> Optional[str]:
    for line in text.splitlines()[:15]:
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
        words     = line.split()
        cap_words = [w for w in words if w and w[0].isupper() and w.isalpha()]
        if 1 <= len(cap_words) <= 4 and 2 <= len(words) <= 5:
            return " ".join(words[:4])
    return None


def extract_skills(text: str, skills_section: str = "") -> List[str]:
    combined = (skills_section + " " + text).lower()
    found: set = set()
    for skill in sorted(SKILLS_LIST, key=len, reverse=True):
        pattern = r"(?<![a-zA-Z0-9+#])" + re.escape(skill) + r"(?![a-zA-Z0-9+#])"
        if re.search(pattern, combined):
            found.add(skill)
    return sorted(found)


def extract_projects(text: str, projects_section: str = "") -> List[str]:
    blocks: List[str] = []

    if projects_section.strip():
        proj_lines    = [l.strip() for l in projects_section.splitlines() if l.strip()]
        current_block: List[str] = []
        for line in proj_lines:
            if re.match(r"^[A-Z]", line) and current_block and len(current_block) >= 2:
                blocks.append(" ".join(current_block[:8]))
                current_block = [line]
            else:
                current_block.append(line)
        if current_block:
            blocks.append(" ".join(current_block[:8]))

    if not blocks:
        lines = text.splitlines()
        for i, line in enumerate(lines):
            if any(kw in line.lower() for kw in PROJECT_KEYWORDS):
                start = max(0, i - 1)
                end   = min(len(lines), i + 10)
                block = " ".join(l.strip() for l in lines[start:end] if l.strip())
                if len(block) > 30:
                    blocks.append(block)
                if len(blocks) >= 6:
                    break

    seen:   set          = set()
    unique: List[str]    = []
    for b in blocks:
        key = b[:60]
        if key not in seen:
            seen.add(key)
            unique.append(b[:300])
    return unique[:6]


def extract_education(text: str, edu_section: str = "") -> List[dict]:
    def _match_keywords(line: str) -> List[str]:
        matches: List[str] = []
        for kw in EDU_KEYWORDS:
            pat = r"(?<![a-zA-Z0-9])" + re.escape(kw) + r"(?![a-zA-Z0-9])"
            if re.search(pat, line, re.IGNORECASE):
                matches.append(kw)
        return matches

    def _infer_institution(line: str) -> str:
        m = re.search(
            r"\b([A-Za-z][A-Za-z\s&\.\-]{2,}(?:college|university|institute|school))\b",
            line,
            re.IGNORECASE,
        )
        if m:
            return m.group(1).strip().lower()
        # fallback bucket so we still dedupe noisy lines
        return line.strip().lower()[:80]

    def _best_keyword(candidates: List[str]) -> str:
        # Prefer explicit forms over abbreviations (e.g., b.sc > ba, m.sc > ms).
        priority = {
            "ph.d": 100, "phd": 99, "m.tech": 95, "b.tech": 94, "m.eng": 93, "b.eng": 92,
            "m.sc": 91, "b.sc": 90, "m.e": 89, "b.e": 88, "mba": 87, "mca": 86, "bca": 85,
            "b.com": 84, "master": 80, "bachelor": 79, "degree": 70, "diploma": 69,
            "ms": 50, "bs": 49, "ma": 48, "ba": 47,
        }
        return sorted(candidates, key=lambda k: (priority.get(k, 0), len(k)), reverse=True)[0]

    def _is_all_caps_heading(line: str) -> bool:
        letters = re.sub(r"[^A-Za-z]", "", line)
        if len(letters) < 3:
            return False
        return letters.isupper()

    # 1) If the caller already extracted an education section, use it directly;
    #    otherwise fall back to scanning the full document by heading.
    if edu_section.strip():
        scan_text = edu_section
    else:
        scan_text = text

    lines = [l.strip() for l in scan_text.splitlines() if l.strip()]
    section_lines: List[str] = []

    if edu_section.strip():
        # edu_section is already the section content — use it as-is
        section_lines = lines
    else:
        # Find education section in the full document by heading
        start_idx = -1
        heading_re = re.compile(r"\b(education|academic|qualification)\b", re.IGNORECASE)
        for i, line in enumerate(lines):
            if heading_re.search(line):
                start_idx = i + 1
                break

        if start_idx != -1:
            for line in lines[start_idx:]:
                # stop at next all-caps heading (e.g., SKILLS, EXPERIENCE)
                if _is_all_caps_heading(line):
                    break
                section_lines.append(line)

    # 2) Parse only section lines when we found a section
    if section_lines:
        results: List[dict] = []
        for line in section_lines:
            kws = _match_keywords(line)
            if not kws:
                continue
            years = sorted(set(YEAR_RE.findall(line)))[:3]
            results.append({"keyword": _best_keyword(kws), "years": years})
        return results

    # 4) Fallback: scan full text but dedupe by institution, keep one best match each
    by_institution: dict = {}
    for line in lines:
        kws = _match_keywords(line)
        if not kws:
            continue
        inst = _infer_institution(line)
        best_kw = _best_keyword(kws)
        years = sorted(set(YEAR_RE.findall(line)))[:3]
        current = by_institution.get(inst)
        if current is None or len(best_kw) > len(current["keyword"]):
            by_institution[inst] = {"keyword": best_kw, "years": years}

    return list(by_institution.values())


def extract_summary(text: str, summary_section: str = "") -> str:
    if summary_section.strip():
        lines = [l.strip() for l in summary_section.splitlines() if l.strip()]
        return " ".join(lines[:4])

    for line in text.splitlines():
        line = line.strip()
        if len(line) < 40:
            continue
        if EMAIL_RE.search(line) or URL_RE.search(line):
            continue
        if re.search(r"\d{7,}", line):
            continue
        return line[:400]
    return ""


def extract_links(text: str) -> dict:
    linkedin = LINKEDIN_RE.search(text)
    github   = GITHUB_RE.search(text)
    return {
        "linkedin": linkedin.group(0) if linkedin else None,
        "github":   github.group(0)   if github   else None,
    }


# ── Column-aware PDF extraction ───────────────────────────────────────────────

def _detect_two_column(words: list, page_width: float) -> tuple:
    """Detect two-column layout using dynamic gap detection.

    Instead of a fixed threshold, finds the largest x0 gap in the
    middle 30-70% of page width.  Returns (is_two_col, split_x).
    """
    if not words or page_width <= 0:
        return False, page_width / 2

    x0_vals = sorted(set(round(w["x0"], 1) for w in words))
    mid_lo  = page_width * 0.30
    mid_hi  = page_width * 0.70

    # Keep only x0 values inside the middle band
    mid_x0s = [x for x in x0_vals if mid_lo <= x <= mid_hi]
    if len(mid_x0s) < 2:
        return False, page_width / 2

    # Find the largest gap between consecutive mid-band x0 values
    best_gap  = 0.0
    best_left = mid_x0s[0]
    for i in range(1, len(mid_x0s)):
        gap = mid_x0s[i] - mid_x0s[i - 1]
        if gap > best_gap:
            best_gap  = gap
            best_left = mid_x0s[i - 1]
            best_right = mid_x0s[i]

    # A gap >= 20pt typically separates two columns in a standard resume
    if best_gap < 20:
        return False, page_width / 2

    # Check 30%/30% clustering rule on each side of the gap midpoint
    split_x  = (best_left + best_right) / 2
    left_ct  = sum(1 for w in words if w["x0"] < split_x)
    right_ct = sum(1 for w in words if w["x0"] >= split_x)
    total    = len(words)
    if total == 0:
        return False, page_width / 2

    if (left_ct / total) > 0.20 and (right_ct / total) > 0.20:
        return True, split_x

    return False, page_width / 2


def _words_to_lines(words: list) -> str:
    """Reconstruct readable text from pdfplumber word dicts.

    Groups words by Y-proximity (±3pt = same line), sorts each line
    left-to-right, then joins lines top-to-bottom.
    """
    if not words:
        return ""

    # Sort by (top, x0)
    words = sorted(words, key=lambda w: (w["top"], w["x0"]))

    lines: list = []
    current_line: list = [words[0]]
    current_top = words[0]["top"]

    for w in words[1:]:
        if abs(w["top"] - current_top) <= 3:
            current_line.append(w)
        else:
            # Flush current line
            current_line.sort(key=lambda w2: w2["x0"])
            lines.append(" ".join(w2["text"] for w2 in current_line))
            current_line = [w]
            current_top  = w["top"]

    # Flush last line
    if current_line:
        current_line.sort(key=lambda w2: w2["x0"])
        lines.append(" ".join(w2["text"] for w2 in current_line))

    return "\n".join(lines)


def _extract_page_text_column_aware(page) -> str:
    """Extract text from a single pdfplumber page with column awareness.

    Column detection runs PER PAGE so page 1 can be two-column while
    page 2 is single-column.
    """
    try:
        words = page.extract_words(keep_blank_chars=False)
    except Exception:
        words = []

    if not words:
        # Fallback — no words extracted at word level
        return page.extract_text(x_tolerance=3, y_tolerance=3) or ""

    is_two_col, split_x = _detect_two_column(words, page.width)

    if not is_two_col:
        # Single-column — use standard extraction for best quality
        return page.extract_text(x_tolerance=3, y_tolerance=3) or ""

    left_words  = [w for w in words if w["x0"] < split_x]
    right_words = [w for w in words if w["x0"] >= split_x]

    left_text  = _words_to_lines(left_words)
    right_text = _words_to_lines(right_words)

    # Left column first, then right column — NOT interleaved
    return left_text + "\n\n" + right_text


def _extract_pdf_text(pdf) -> str:
    """Extract text from a pdfplumber PDF with per-page column detection."""
    pages_text = []
    for page in pdf.pages:
        t = _extract_page_text_column_aware(page)
        if t:
            pages_text.append(t)
    return "\n".join(pages_text)


# ── Master builder ────────────────────────────────────────────────────────────

def build_parsed_schema(filename: str, raw_text: str) -> dict:
    if not raw_text or not raw_text.strip():
        return {"error": "Empty text extracted from resume", "filename": filename}

    sections = split_sections(raw_text)

    skills_section = "\n".join(sections.get("skills",     []))
    proj_section   = "\n".join(sections.get("projects",   []))
    edu_section    = "\n".join(sections.get("education",  []))
    exp_section    = "\n".join(sections.get("experience", []))
    sum_section    = "\n".join(sections.get("summary",    []))

    email_match = EMAIL_RE.search(raw_text)
    phones      = list({
        m.group(0) for m in PHONE_RE.finditer(raw_text)
        if len(re.sub(r"\D", "", m.group(0))) >= 7
    })[:3]
    links = extract_links(raw_text)

    return {
        "filename":           filename,
        "name":               extract_name(raw_text),
        "email":              email_match.group(0) if email_match else None,
        "phones":             sorted(phones),
        "linkedin":           links["linkedin"],
        "github":             links["github"],
        "skills":             extract_skills(raw_text, skills_section),
        "education":          extract_education(raw_text, edu_section),
        "projects":           extract_projects(raw_text, proj_section),
        "experience_section": exp_section[:1000],
        "summary":            extract_summary(raw_text, sum_section),
        "raw_text_excerpt":   raw_text[:3000],
        "full_text_length":   len(raw_text),
    }


# ── Endpoint ──────────────────────────────────────────────────────────────────

@router.post("/parse/resume/{session_id}")
async def parse_resume(session_id: str):
    resume_dir  = _storage_dir() / session_id / "resumes"

    if not resume_dir.exists():
        raise HTTPException(status_code=404, detail="Resume directory not found.")

    files = [f for f in resume_dir.iterdir() if f.is_file()]
    if not files:
        raise HTTPException(status_code=404, detail="No resume file found. Upload a resume first.")

    resume_path = files[0]
    raw_text    = ""

    try:
        if resume_path.suffix.lower() == ".pdf":
            with pdfplumber.open(resume_path) as pdf:
                raw_text = _extract_pdf_text(pdf)

        elif resume_path.suffix.lower() in (".docx", ".doc"):
            # DOCX extraction does not have column separation issues —
            # python-docx / docx2txt reads paragraphs sequentially.
            raw_text = docx2txt.process(str(resume_path))

        else:
            raw_text = resume_path.read_text(encoding="utf-8", errors="ignore")

    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to read resume: {exc}")

    if not raw_text or not raw_text.strip():
        raise HTTPException(
            status_code=422,
            detail=(
                "Could not extract text from the resume. "
                "The file may be image-based, password-protected, or corrupted."
            ),
        )

    parsed = build_parsed_schema(resume_path.name, raw_text)
    if "error" in parsed:
        raise HTTPException(status_code=422, detail=parsed["error"])

    out_file = _storage_dir() / session_id / "parsed_resume.json"
    out_file.write_text(json.dumps(parsed, indent=2, ensure_ascii=False), encoding="utf-8")

    return {
        "status":          "ok",
        "parsed_path":     str(out_file),
        "name":            parsed["name"],
        "email":           parsed["email"],
        "skills":          parsed["skills"],
        "projects_count":  len(parsed["projects"]),
        "education_count": len(parsed["education"]),
    }
