"""
Unified scorecard endpoint.
"""

import json
from pathlib import Path
from typing import Any, Dict, List

from fastapi import APIRouter, HTTPException

router = APIRouter()


def _storage_dir() -> Path:
    return Path(__file__).resolve().parents[4] / "storage"

def _read_json(p: Path) -> Dict[str, Any]:
    return json.loads(p.read_text(encoding="utf-8"))

def _safe_read(p: Path) -> Dict[str, Any]:
    if not p.exists():
        return {}
    try:
        return _read_json(p)
    except Exception:
        return {}


@router.get("/report/{session_id}")
async def get_full_report(session_id: str):
    sdir = _storage_dir() / session_id
    if not sdir.exists():
        raise HTTPException(status_code=404, detail="session not found")

    final_report = _safe_read(sdir / "final_report.json")
    if not final_report:
        raise HTTPException(
            status_code=404,
            detail="final_report.json not found. Call /api/aggregate first.",
        )

    analytics  = _safe_read(sdir / "analytics_report.json")
    decision   = _safe_read(sdir / "final_decision.json")

    # Suggestions
    suggestions: List[str] = []
    reviewer = analytics.get("reviewer_summary", {})
    recs = reviewer.get("recommendation", [])
    if isinstance(recs, list):
        suggestions += recs
    elif isinstance(recs, str):
        suggestions += recs.splitlines()

    seen:     set       = set()
    unique_s: List[str] = []
    for s in suggestions:
        s = s.strip()
        if s and s not in seen:
            seen.add(s)
            unique_s.append(s)

    # Candidate info — merge parsed resume name with profile name as fallback
    parsed = _safe_read(sdir / "parsed_resume.json")
    jd     = _safe_read(sdir / "job_description.json")
    prof   = _safe_read(sdir / "candidate_profile.json")

    candidate_info = {
        # Prefer resume-extracted name; fall back to user-typed name from profile
        "name":            parsed.get("name") or prof.get("name", "Candidate"),
        "email":           parsed.get("email", ""),
        "job_role":        jd.get("job_role", ""),
        "company":         jd.get("company", ""),
        "expertise_level": prof.get("expertise_level", "fresher"),
    }

    return {
        "status":             "ok",
        "session_id":         session_id,
        "candidate":          candidate_info,
        "final_score":        final_report.get("final_score"),
        "verdict":            final_report.get("verdict"),
        "pass_threshold":     final_report.get("pass_threshold"),
        "needs_human_review": final_report.get("needs_human_review"),
        "coverage_pct":       final_report.get("coverage_pct"),
        "questions_counted":  final_report.get("questions_counted"),
        "expected_questions": final_report.get("expected_questions"),
        "total_questions_answered": final_report.get("total_questions_answered"),
        "per_type_summary":   final_report.get("per_type_summary", {}),
        "skill_coverage":     final_report.get("skill_coverage", {}),
        "question_breakdown": final_report.get("question_breakdown", []),
        "decision":           decision.get("decision"),
        "confidence":         decision.get("confidence"),
        "readiness_level":    decision.get("readiness_level"),
        "decision_reasons":   decision.get("reasons", []),
        "skills_analysis":    analytics.get("skills_analysis", {}),
        "strengths":          final_report.get("strengths", analytics.get("strengths", [])),
        "weak_areas":         final_report.get("weak_areas", analytics.get("weak_areas", [])),
        "not_assessed":       final_report.get("not_assessed", analytics.get("not_assessed", [])),
        "answer_quality":     analytics.get("answer_quality", {}),
        "reviewer_summary":   analytics.get("reviewer_summary", {}),
        "readiness_index":    analytics.get("readiness_index", {}),
        "followup_analysis":  analytics.get("followup_analysis", {}),
        "filler_word_summary": final_report.get("filler_word_summary", {}),
        "posture_summary":    final_report.get("posture_summary", {}),
        "violations_summary": final_report.get("violations_summary", {}),
        "suggestions":        unique_s[:6],
    }
