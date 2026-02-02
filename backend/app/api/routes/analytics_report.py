from fastapi import APIRouter, HTTPException
from pathlib import Path
import json
from typing import Dict, Any, List
from collections import defaultdict

router = APIRouter()

STOP_WORDS = {
    "used", "use", "using",
    "actually", "overall", "good", "goood",
    "days", "day", "college", "questions",
    "role", "solved", "based",
    "experience", "little", "biggest",
    "looking", "strong", "learning", "machine"
}


# -----------------------------
# Helpers
# -----------------------------

def _base_dir() -> Path:
    return Path(__file__).resolve().parents[5]

def _storage_dir() -> Path:
    return _base_dir() / "storage"

def _read_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))

def _safe_avg(vals: List[float]):
    return round(sum(vals) / len(vals), 2) if vals else None

def _risk_from_avg(avg: float):
    if avg is None:
        return "UNKNOWN"
    if avg >= 7.5:
        return "LOW"
    if avg >= 6.5:
        return "MEDIUM"
    return "HIGH"

def _load_skill_whitelist(session_dir: Path) -> set:
    """
    Load allowed skills from resume + job description.
    Only these skills can appear in analytics.
    """
    skills = set()

    parsed_resume = session_dir / "parsed_resume.json"
    job_desc = session_dir / "job_description.json"

    if parsed_resume.exists():
        data = json.loads(parsed_resume.read_text(encoding="utf-8"))
        for s in data.get("skills", []):
            skills.add(s.lower())

    if job_desc.exists():
        jd = json.loads(job_desc.read_text(encoding="utf-8"))
        jd_text = (
            jd.get("job_role", "") + " " +
            jd.get("job_description", "")
        ).lower()

        for skill in list(skills):
            if skill in jd_text:
                skills.add(skill)

    return skills



# -----------------------------
# Main Analytics Endpoint
# -----------------------------

@router.post("/analytics/{session_id}")
async def generate_analytics(session_id: str):
    session_dir = _storage_dir() / session_id
    if not session_dir.exists():
        raise HTTPException(status_code=404, detail="session not found")

    final_report_path = session_dir / "final_report.json"
    if not final_report_path.exists():
        raise HTTPException(status_code=404, detail="final_report.json not found")

    final_report = _read_json(final_report_path)

    scores = final_report.get("scores", {})
    needs_human_questions = set(final_report.get("needs_human_questions", []))

    # -----------------------------
    # 6.2.1 Skill-wise Analysis
    # -----------------------------

    skill_scores = defaultdict(list)
    skill_followups = defaultdict(int)
    skill_review_flags = defaultdict(int)

    whitelist = _load_skill_whitelist(session_dir)

    for qid, data in scores.items():
        qtype = data.get("question_type")
        raw = data.get("raw_score")
        meta_tokens = [t["token"].lower() for t in data.get("top_matches", [])]

        for token in meta_tokens:
            token = token.strip()

            # 🚫 ignore garbage words
            if token in STOP_WORDS:
                continue

            # 🚫 ignore anything not in resume/JD
            if token not in whitelist:
                continue

            skill_scores[token].append(raw)

            if qtype == "followup":
                skill_followups[token] += 1

            if qid in needs_human_questions:
                skill_review_flags[token] += 1


    skills_analysis = {}
    for skill, vals in skill_scores.items():
        avg = _safe_avg(vals)
        skills_analysis[skill] = {
            "avg_score": avg,
            "questions": len(vals),
            "followups": skill_followups.get(skill, 0),
            "needs_review": skill_review_flags.get(skill, 0),
            "risk": _risk_from_avg(avg)
        }

    # -----------------------------
    # 6.2.2 Follow-up Pressure
    # -----------------------------

    total_questions = len(scores)
    total_followups = sum(1 for s in scores.values() if s.get("question_type") == "followup")

    followup_analysis = {
        "total_questions": total_questions,
        "total_followups": total_followups,
        "followup_ratio": round(total_followups / total_questions, 2) if total_questions else 0,
        "by_skill": dict(skill_followups)
    }

    # -----------------------------
    # 6.2.3 Answer Quality Signals
    # -----------------------------

    similarities = []
    low_score_count = 0

    for data in scores.values():
        sim = data.get("similarity")
        raw = data.get("raw_score")

        if sim is not None:
            similarities.append(sim)
        if raw is not None and raw < 6.5:
            low_score_count += 1

    answer_quality = {
        "avg_similarity": round(sum(similarities) / len(similarities), 2) if similarities else None,
        "low_score_answers": low_score_count,
        "consistency": (
            "HIGH" if low_score_count <= 2
            else "MEDIUM" if low_score_count <= 5
            else "LOW"
        ),
        "risk_signal": (
            "DEPTH_VARIANCE" if low_score_count > 3
            else "STABLE"
        )
    }

    # -----------------------------
    # 6.2.4 Reviewer Summary
    # -----------------------------

    strengths = []
    concerns = []

    for skill, data in skills_analysis.items():
        if data["risk"] == "LOW":
            strengths.append(f"Strong understanding of {skill}")
        if data["risk"] == "HIGH":
            concerns.append(f"Inconsistent depth in {skill}")

    if not strengths:
        strengths.append("General technical foundation is acceptable")

    if not concerns:
        concerns.append("No major red flags detected")

    reviewer_summary = {
        "overall": (
            "Candidate demonstrates solid fundamentals with uneven depth across skills."
            if final_report.get("needs_human_review")
            else "Candidate performance is consistent and meets expectations."
        ),
        "strengths": strengths[:5],
        "concerns": concerns[:5],
        "recommendation": (
            "Human review recommended before final decision."
            if final_report.get("needs_human_review")
            else "Suitable for proceeding to next stage."
        )
    }

    # -----------------------------
    # 6.2.5 Readiness Index
    # -----------------------------

    final_score = final_report.get("final_score", 0)

    if final_score >= 8:
        level = "MID-SENIOR"
    elif final_score >= 6.5:
        level = "JUNIOR-MID"
    else:
        level = "ENTRY"

    readiness_index = {
        "level": level,
        "confidence": round(min(1.0, final_score / 10), 2),
        "risk": (
            "HIGH" if final_report.get("needs_human_review")
            else "LOW"
        ),
        "interview_quality": (
            "EXCELLENT" if final_score >= 8
            else "GOOD" if final_score >= 6.5
            else "WEAK"
        )
    }

    # -----------------------------
    # Final Analytics Report
    # -----------------------------

    analytics_report = {
        "session_id": session_id,
        "skills_analysis": skills_analysis,
        "followup_analysis": followup_analysis,
        "answer_quality": answer_quality,
        "reviewer_summary": reviewer_summary,
        "readiness_index": readiness_index
    }

    out_path = session_dir / "analytics_report.json"
    out_path.write_text(json.dumps(analytics_report, indent=2), encoding="utf-8")

    return {
        "status": "ok",
        "analytics_path": str(out_path),
        "readiness_level": readiness_index["level"]
    }
