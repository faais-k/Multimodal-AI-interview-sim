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
from backend.app.core.validation import validate_session_id

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
    "summary":        re.compile(r"^\s*(summary|objective|profile|about me|career objective|professional summary)\s*$", re.IGNORECASE),
    "skills":         re.compile(r"^\s*(skills?|technical skills?|core competencies|technologies|tech stack|expertise|key skills|programming languages|tools)\s*$", re.IGNORECASE),
    "experience":     re.compile(r"^\s*(experience|work experience|employment|professional experience|work history|internship|career history)\s*$", re.IGNORECASE),
    "education":      re.compile(r"^\s*(education|academic|qualification|degree|educational background|academic background|university|college)\s*$", re.IGNORECASE),
    "projects":       re.compile(r"^\s*(projects?|personal projects?|academic projects?|key projects?|side projects?|portfolio|notable projects)\s*$", re.IGNORECASE),
    "certifications": re.compile(r"^\s*(certifications?|certificates?|courses?|training|achievements?|awards?|publications?)\s*$", re.IGNORECASE),
}

EDU_KEYWORDS = [
    "bachelor", "master", "b.sc", "m.sc", "b.tech", "m.tech", "b.e", "m.e",
    "bs", "ms", "ba", "ma", "phd", "ph.d", "mba", "degree", "diploma",
    "b.com", "bca", "mca", "b.eng", "m.eng", "b.s.", "m.s.", "b.a.", "m.a.",
    "high school", "secondary", "senior secondary", "12th", "10th", "ssc", "hsc",
    "university", "college", "institute", "academy", "school", "polytechnic",
    "cgpa", "percentage", "gpa", "grade", "first class", "distinction",
    "computer science", "information technology", "electronics", "electrical",
    "mechanical", "civil", "biotechnology", "data science",
]

PROJECT_KEYWORDS = [
    "project", "built", "developed", "implemented", "created", "designed",
    "contributed", "deployed", "architected", "engineered", "launched",
    "published", "shipped", "delivered", "maintained", "optimized",
    "enhanced", "upgraded", "refactored", "automated", "integrated",
    "github.com", "gitlab.com", "bitbucket.org", "demo", "live", "production",
]

# Negative keywords to exclude education entries from projects
EDU_NEGATIVE_KEYWORDS = [
    "bachelor", "master", "b.sc", "m.sc", "b.tech", "m.tech", "b.e", "m.e",
    "bs", "ms", "ba", "ma", "phd", "ph.d", "mba", "degree", "diploma",
    "cgpa", "gpa", "percentage", "grade", "university", "college", "institute",
    "academy", "passed", "graduated", "matriculation", "secondary", "high school",
    "coursework", "thesis", "dissertation", "academic", "semester", "batch",
]

# ── Skills list ───────────────────────────────────────────────────────────────
# NOTE: single-letter "c" removed — too ambiguous (matches "scientific", etc.)
# Use "c language" or "c programming" instead.
SKILLS_LIST = [
    # Languages
    "python", "java", "javascript", "typescript", "c language", "c programming",
    "c++", "c#", "go", "golang", "rust", "ruby", "php", "swift", "kotlin",
    "scala", "r", "matlab", "perl", "dart", "lua", "haskell", "elixir", "clojure",
    "objective-c", "groovy", "vb.net", "vba", "sas", "abap", "apex", "julia",
    # ML/AI
    "pytorch", "tensorflow", "keras", "scikit-learn", "sklearn",
    "machine learning", "deep learning", "nlp", "natural language processing",
    "computer vision", "reinforcement learning", "transformers", "bert", "gpt",
    "llm", "llama", "langchain", "huggingface", "xgboost", "lightgbm", "catboost",
    "pandas", "numpy", "scipy", "matplotlib", "seaborn", "plotly", "streamlit",
    "openai", "stable diffusion", "generative ai", "gemini", "claude", "ollama",
    "mlflow", "kubeflow", "labelbox", "roboflow", "detectron2", "spacy", "nltk",
    "tokenization", "embeddings", "vector database", "pinecone", "weaviate",
    "chroma", "faiss", "milvus", "qdrant", "annoy", "hnsw",
    # Web
    "react", "react.js", "vue", "vue.js", "angular", "nextjs", "nuxtjs", "svelte",
    "sveltekit", "solidjs", "preact", "alpine.js", "htmx", "jquery",
    "nodejs", "node.js", "express", "fastapi", "flask", "django", "tornado",
    "spring", "spring boot", "springboot", "quarkus", "micronaut",
    "laravel", "symfony", "codeigniter", "cakephp", "rails", "ruby on rails",
    "asp.net", "asp.net core", "blazor", "razor", "mvc", "webapi",
    "graphql", "apollo", "trpc", "rest api", "restful", "soap", "grpc",
    "websocket", "socket.io", "pusher", "signalr",
    "html", "html5", "css", "css3", "sass", "scss", "less",
    "tailwind", "bootstrap", "material-ui", "mui", "chakra-ui", "antd",
    "styled-components", "emotion", "postcss", "autoprefixer",
    # Data / DB
    "sql", "mysql", "mariadb", "postgresql", "postgres", "sqlite", "oracle",
    "mongodb", "mongoose", "redis", "cassandra", "cockroachdb", "cockroach",
    "elasticsearch", "solr", "meilisearch", "algolia",
    "firebase", "firestore", "dynamodb", "cosmos db", "cosmosdb",
    "neo4j", "arangodb", "orientdb", "supabase", "planetscale", "neon",
    "prisma", "typeorm", "sequelize", "sqlalchemy", "peewee", "hibernate",
    "entity framework", "ef core", "dapper", "jpa", "jdbc", "odbc",
    "spark", "hadoop", "hdfs", "yarn", "kafka", "kafka streams", "airflow",
    "dbt", "snowflake", "bigquery", "redshift", "databricks", "delta lake",
    "tableau", "power bi", "powerbi", "looker", "metabase", "grafana",
    "pentaho", "talend", "informatica", "ssis", "ssrs", "ssas",
    # DevOps / Cloud
    "docker", "containerd", "podman", "lxc",
    "kubernetes", "k8s", "helm", "kustomize", "istio", "linkerd",
    "terraform", "terragrunt", "pulumi", "crossplane",
    "ansible", "puppet", "chef", "saltstack",
    "jenkins", "github actions", "gitlab ci", "azure devops", "circleci",
    "travis ci", "drone", "argo cd", "flux", "spinnaker",
    "aws", "amazon web services", "ec2", "ecs", "eks", "lambda", "s3",
    "rds", "sqs", "sns", "eventbridge", "step functions", "api gateway",
    "cloudformation", "cloudwatch", "iam", "route53", "cloudfront",
    "gcp", "google cloud", "compute engine", "gke", "cloud run", "cloud functions",
    "bigquery", "pub/sub", "dataflow", "dataproc",
    "azure", "azure app service", "azure functions", "aks", "azure devops",
    "heroku", "railway", "render", "fly.io", "vercel", "netlify", "surge",
    "linux", "ubuntu", "centos", "debian", "redhat", "rhel", "fedora",
    "bash", "zsh", "shell scripting", "powershell", "awk", "sed",
    "nginx", "apache", "httpd", "tomcat", "iis", "caddy", "traefik",
    "ha proxy", "haproxy", "varnish", "squid",
    "ci/cd", "cicd", "devops", "devsecops", "sre", "site reliability",
    "microservices", "monolith", "serverless", "paas", "iaas", "faas",
    "observability", "monitoring", "logging", "tracing", "opentelemetry",
    "prometheus", "thanos", "loki", "jaeger", "zipkin", "new relic",
    "datadog", "sentry", "bugsnag", "rollbar", "pagerduty", "opsgenie",
    # Mobile
    "android", "ios", "react native", "flutter", "xamarin", "cordova",
    "phonegap", "ionic", "capacitor", "swiftui", "jetpack compose",
    "kotlin multiplatform", "kmp", "realm", "coredata", "sqlite",
    # Testing
    "unit testing", "integration testing", "e2e testing", "end to end testing",
    "jest", "mocha", "chai", "cypress", "playwright", "selenium", "webdriver",
    "pytest", "unittest", "junit", "testng", "nunit", "xunit", "moq",
    "cucumber", "bdd", "tdd", "atdd", "specflow", "robot framework",
    "postman", "insomnia", "restassured", "karate", "soapui",
    "k6", "jmeter", "loadrunner", "artillery", "locust",
    # Security
    "oauth", "oauth2", "openid connect", "oidc", "saml", "jwt", "auth0",
    "keycloak", "okta", "azure ad", "active directory", "ldap",
    "encryption", "hashing", "tls", "ssl", "https", "certificates",
    "penetration testing", "vulnerability scanning", "owasp", "security",
    "burp suite", "metasploit", "nmap", "wireshark", "kali linux",
    # CV
    "opencv", "pillow", "mediapipe", "yolo", "yolov8", "yolov5", "object detection",
    "image processing", "video processing", "ffmpeg", "computer vision",
    "ocr", "tesseract", "opencv-python", "scikit-image", "scikit-image",
    # Tools / Platform
    "git", "github", "gitlab", "bitbucket", "azure repos", "svn", "mercurial",
    "jira", "confluence", "trello", "asana", "monday", "notion", "linear",
    "slack", "teams", "discord", "zoom", "google meet", "webex",
    "figma", "sketch", "adobe xd", "invision", "framer", "proto.io",
    "photoshop", "illustrator", "after effects", "premiere", "indesign",
    "blender", "maya", "3ds max", "cinema 4d", "zbrush", "substance",
    "unity", "unreal engine", "unreal", "godot", "gamemaker", "cryengine",
    # Blockchain / Web3
    "solidity", "vyper", "rust", "move", "cairo",
    "blockchain", "web3", "ethereum", "bitcoin", "polygon", "solana",
    "cardano", "avalanche", "fantom", "arbitrum", "optimism", "zksync",
    "smart contracts", "defi", "nft", "dao", "hardhat", "foundry",
    "truffle", "ganache", "brownie", "ape", "alchemy", "infura",
    "the graph", "chainlink", "openzeppelin", "erc20", "erc721", "erc1155",
    "metamask", "walletconnect", "ipfs", "filecoin", "arweave",
    # Methodologies / Soft Skills
    "agile", "scrum", "kanban", "lean", "xp", "extreme programming",
    "waterfall", "spiral", "iterative", "incremental", "devops", "cicd",
    "okr", "kpi", "roadmapping", "stakeholder management", "mentoring",
    "leadership", "team management", "cross-functional", "communication",
    "problem solving", "critical thinking", "analytical skills", "creativity",
    "time management", "prioritization", "collaboration", "pair programming",
    "code review", "technical writing", "documentation", "presentation",
    # Architecture / Design
    "system design", "distributed systems", "scalability", "high availability",
    "fault tolerance", "load balancing", "caching", "cdn", "edge computing",
    "event-driven", "message queue", "pub sub", "saga pattern", "cqrs",
    "event sourcing", "ddd", "domain driven design", "clean architecture",
    "hexagonal architecture", "onion architecture", "micro frontends",
    "soa", "service oriented architecture", "esb", "api gateway",
    # Additional Frameworks/Libraries
    "rxjava", "reactivex", "rxjs", "ktor", "vert.x", "quarkus",
    "netty", "jetty", "undertow", "electron", "tauri", "neutralino",
    "nw.js", "cef", "qt", "pyqt", "pyside", "tkinter", "wxpython",
    "electron", "capacitor", "react native web", "expo", "detox",
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


def _contains_edu_keywords(text: str) -> bool:
    """Check if text contains education-related keywords that should exclude it from projects."""
    text_lower = text.lower()
    return any(kw in text_lower for kw in EDU_NEGATIVE_KEYWORDS)


def _is_likely_project(text: str) -> bool:
    """Check if text contains strong project indicators (github links, tech stack, deployment)."""
    text_lower = text.lower()
    strong_indicators = [
        "github.com", "gitlab.com", "bitbucket.org", "demo", "live link",
        "deployed", "hosted on", "available at", "try it", "source code",
        "repository", "repo", "play store", "app store", "chrome extension",
        "npm", "pypi", "docker hub", "vercel.app", "netlify.app", "herokuapp",
        "youtube", "video demo", "screenshot", "architecture", "designed",
    ]
    return any(ind in text_lower for ind in strong_indicators)


def extract_projects(text: str, projects_section: str = "") -> List[str]:
    blocks: List[str] = []

    # Heuristic 1: Look for bullet points or project titles in the projects section
    if projects_section.strip():
        lines = [l.strip() for l in projects_section.splitlines() if l.strip()]
        current_block = []
        
        for line in lines:
            # Skip lines that look like education entries
            if _contains_edu_keywords(line):
                if current_block:
                    block_text = " ".join(current_block)
                    if len(block_text) > 40 and len(block_text.split()) > 5:
                        blocks.append(block_text)
                    current_block = []
                continue
            
            # Check if line starts with a bullet point
            is_bullet = bool(re.match(r"^[\-\*\•\▪\>◦▸▹]\s*", line))
            # Or if it looks like a standalone project title (short, capitalized words, with tech indicators)
            is_title = (len(line) < 80 and 
                       sum(1 for w in line.split() if w and w[0].isupper()) >= 2 and
                       not any(kw in line.lower() for kw in ["bachelor", "master", "degree", "university"]))
            
            if (is_bullet or is_title) and current_block:
                block_text = " ".join(current_block)
                # Filter: must be long enough, not contain education keywords, and describe something technical
                if (len(block_text) > 40 and 
                    len(block_text.split()) > 5 and
                    not _contains_edu_keywords(block_text) and
                    (_is_likely_project(block_text) or any(kw in block_text.lower() for kw in PROJECT_KEYWORDS))):
                    blocks.append(block_text)
                
                if is_title:
                    current_block = [line]
                else:
                    current_block = [re.sub(r"^[\-\*\•\▪\>◦▸▹]\s*", "", line)]
            else:
                if is_bullet:
                    line = re.sub(r"^[\-\*\•\▪\>◦▸▹]\s*", "", line)
                current_block.append(line)
                
        if current_block:
            block_text = " ".join(current_block)
            if (len(block_text) > 40 and 
                len(block_text.split()) > 5 and
                not _contains_edu_keywords(block_text) and
                (_is_likely_project(block_text) or any(kw in block_text.lower() for kw in PROJECT_KEYWORDS))):
                blocks.append(block_text)

    # Heuristic 2: Fallback to searching full text for project keywords with stricter filtering
    if not blocks:
        lines = text.splitlines()
        for i, line in enumerate(lines):
            line_lower = line.lower()
            # Skip if contains education keywords
            if _contains_edu_keywords(line):
                continue
            # Require strong project indicators in fallback mode
            if any(kw in line_lower for kw in ["github.com", "project", "built", "developed"]) and len(line) > 20:
                start = max(0, i)
                end   = min(len(lines), i + 4)
                block = " ".join(l.strip() for l in lines[start:end] if l.strip())
                if (len(block) > 50 and 
                    len(block.split()) > 6 and
                    not _contains_edu_keywords(block) and
                    _is_likely_project(block)):
                    blocks.append(block)
                if len(blocks) >= 6:
                    break

    # Deduplicate and clean up
    seen: set = set()
    unique: List[str] = []
    for b in blocks:
        b = re.sub(r"\s+", " ", b).strip()
        key = b[:50].lower()
        if key not in seen and len(b) >= 50:
            seen.add(key)
            unique.append(b[:500])
            
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
            r"\b([A-Za-z][A-Za-z\s&\.\-]{2,}(?:college|university|institute|school|academy|polytechnic))\b",
            line,
            re.IGNORECASE,
        )
        if m:
            return m.group(1).strip().title()
        # fallback bucket so we still dedupe noisy lines
        return line.strip().title()[:80]

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
    validate_session_id(session_id)
    resume_dir  = _storage_dir() / session_id / "resumes"

    if not resume_dir.exists():
        raise HTTPException(status_code=404, detail="Resume directory not found.")

    files = sorted(
        [f for f in resume_dir.iterdir() if f.is_file()],
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
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
