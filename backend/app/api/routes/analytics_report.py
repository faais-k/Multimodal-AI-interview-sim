"""
Analytics report generation.

P2-B: _llm_generate_suggestions() generates specific, actionable improvement
suggestions using the LLM with real interview data (weak scores, what_was_missing,
not-assessed skills). Falls back to template recommendations if LLM unavailable.
"""
import json
import re
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List

from fastapi import APIRouter, HTTPException
from backend.app.core.validation import validate_session_id

router = APIRouter()

STOP_WORDS = {
    "used", "use", "using",
    "actually", "overall", "good", "goood",
    "days", "day", "college", "questions",
    "role", "solved", "based",
    "experience", "little", "biggest",
    "looking", "strong", "learning", "machine",
}


def _storage_dir() -> Path:
    from backend.app.core.storage import get_storage_dir
    return get_storage_dir()

def _read_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))

def _safe_avg(vals: List[float]):
    return round(sum(vals) / len(vals), 2) if vals else None

def _risk_from_avg(avg):
    if avg is None:  return "UNKNOWN"
    if avg >= 7.5:   return "LOW"
    if avg >= 6.5:   return "MEDIUM"
    return "HIGH"


# ── P2-B: LLM-generated personalised suggestions ──────────────────────────────

def _llm_generate_suggestions(
    candidate_name: str,
    job_role: str,
    expertise_level: str,
    question_breakdown: list,
    weak_areas: list,
    not_assessed: list,
    skills_analysis: dict,
) -> list:
    """Generate personalised improvement suggestions using the LLM.

    Uses weak answer scores, what_was_missing fields from LLM evaluations,
    and not-assessed resume skills to produce specific, actionable advice.

    Returns a list of suggestion strings, or [] if LLM unavailable.
    Template recommendations remain as fallback when [] is returned.
    """
    try:
        from backend.app.core.ml_models import get_llm_model, llm_generate

        model, _ = get_llm_model()
        if model is None:
            return []

        # Build compact summary of weak answers using LLM evaluation data
        weak_answers_summary = []
        for item in question_breakdown:
            if item.get("skipped") is True:
                continue
            score = item.get("score", 0) or 0
            if score < 6.5:
                llm_eval = item.get("llm_evaluation") or {}
                missing  = llm_eval.get("what_was_missing", "") or ""
                weak_answers_summary.append(
                    f"- {item.get('skill_target', 'unknown')}: "
                    f"score {score}/10. Missing: {missing or 'unclear'}"
                )

        weak_summary      = "\n".join(weak_answers_summary[:5]) or "No specific weak answers identified"
        weak_str          = ", ".join(weak_areas[:5]) or "none"
        not_assessed_str  = ", ".join(not_assessed[:8]) or "none"

        prompt = f"""You are a career coach providing specific, actionable feedback after a mock interview.

CANDIDATE: {candidate_name}
ROLE: {job_role}
LEVEL: {expertise_level}

WEAK ANSWERS (scored below 6.5/10):
{weak_summary}

SKILLS THAT NEED WORK: {weak_str}
SKILLS ON RESUME NOT TESTED: {not_assessed_str}

Write exactly 4 specific, actionable improvement suggestions.
Each suggestion must:
- Be 1-2 sentences maximum
- Reference a specific skill or concept from the data above
- Be actionable (tell them WHAT to study or practice, not just "improve X")
- Be realistic for their level ({expertise_level})

Respond ONLY with a JSON array of 4 strings:
["suggestion 1", "suggestion 2", "suggestion 3", "suggestion 4"]

Do not add any other text."""

        raw = llm_generate(prompt, max_new_tokens=300, temperature=0.0)

        match = re.search(r'\[[\s\S]*?\]', raw)
        if match:
            result = json.loads(match.group(0))
            if isinstance(result, list) and all(isinstance(s, str) for s in result):
                return result[:6]

    except Exception:
        pass

    return []


@router.post("/analytics/{session_id}")
async def generate_analytics(session_id: str):
    validate_session_id(session_id)
    session_dir = _storage_dir() / session_id
    if not session_dir.exists():
        raise HTTPException(status_code=404, detail="session not found")

    fr_path = session_dir / "final_report.json"
    if not fr_path.exists():
        raise HTTPException(status_code=404, detail="final_report.json not found. Call /aggregate first.")

    final_report = _read_json(fr_path)

    if "question_breakdown" not in final_report or not final_report["question_breakdown"]:
        raise HTTPException(
            status_code=412,
            detail="Aggregate step must run before analytics. Call /aggregate/{id} first."
        )

    scores                = final_report.get("scores", {})
    needs_human_questions = set(final_report.get("needs_human_questions", []))
    parsed_resume         = _read_json(session_dir / "parsed_resume.json") if (session_dir / "parsed_resume.json").exists() else {}
    resume_skills         = [str(s).strip().lower() for s in parsed_resume.get("skills", []) if str(s).strip()]

    # Read candidate info for LLM suggestions
    prof_path       = session_dir / "candidate_profile.json"
    candidate_name  = parsed_resume.get("name") or "Candidate"
    job_role        = ""
    expertise_level = "intermediate"
    if prof_path.exists():
        try:
            prof            = _read_json(prof_path)
            candidate_name  = prof.get("name") or candidate_name
            expertise_level = prof.get("expertise_level", "intermediate")
        except Exception:
            pass
    jd_path = session_dir / "job_description.json"
    if jd_path.exists():
        try:
            jd       = _read_json(jd_path)
            job_role = jd.get("job_role", "")
        except Exception:
            pass

    skill_scores: Dict[str, List[float]] = {s: [] for s in resume_skills}
    skill_followups    = defaultdict(int)
    skill_review_flags = defaultdict(int)

    for qid, data in scores.items():
        qtype        = data.get("question_type")
        raw          = data.get("raw_score")
        skill_target = str(data.get("skill_target", "")).strip().lower()
        if not skill_target:
            continue
        if skill_target not in skill_scores:
            skill_scores[skill_target] = []
        if raw is not None:
            skill_scores[skill_target].append(raw)
        if qtype == "followup":
            skill_followups[skill_target] += 1
        if qid in needs_human_questions:
            skill_review_flags[skill_target] += 1

    skills_analysis = {}
    all_skill_keys  = list(dict.fromkeys(list(skill_scores.keys()) + resume_skills))
    for skill in all_skill_keys:
        vals   = skill_scores.get(skill, [])
        avg    = _safe_avg(vals)
        tested = len(vals) > 0
        skills_analysis[skill] = {
            "avg_score":    avg,
            "questions":    len(vals),
            "followups":    skill_followups.get(skill, 0),
            "needs_review": bool(skill_review_flags.get(skill, 0)),
            "risk":         _risk_from_avg(avg),
            "tested":       tested,
            "status":       "assessed" if tested else "not_assessed",
        }

    total_questions = len(scores)
    total_followups = sum(1 for s in scores.values() if s.get("question_type") == "followup")

    followup_analysis = {
        "total_questions": total_questions,
        "total_followups": total_followups,
        "followup_ratio":  round(total_followups / total_questions, 2) if total_questions else 0,
        "by_skill":        dict(skill_followups),
    }

    similarities    = []
    low_score_count = 0
    for data in scores.values():
        sim = data.get("similarity")
        raw = data.get("raw_score")
        if sim is not None:
            similarities.append(sim)
        if raw is not None and raw < 6.5:
            low_score_count += 1

    answer_quality = {
        "avg_similarity":    round(sum(similarities) / len(similarities), 2) if similarities else None,
        "low_score_answers": low_score_count,
        "consistency":       "HIGH" if low_score_count <= 2 else "MEDIUM" if low_score_count <= 5 else "LOW",
        "risk_signal":       "DEPTH_VARIANCE" if low_score_count > 3 else "STABLE",
    }

    strengths    = []
    concerns     = []
    weak_areas   = []
    not_assessed = []
    for skill, data in skills_analysis.items():
        if not data.get("tested"):
            not_assessed.append(skill)
            continue
        if (data.get("avg_score") or 0) >= 7.5:
            strengths.append(skill)
        if (data.get("avg_score") or 10) < 6.5:
            weak_areas.append(skill)
            concerns.append(f"Inconsistent depth in {skill}")

    question_breakdown = final_report.get("question_breakdown", [])
    weak_skill_topics: Dict[str, str] = {}
    for qb in question_breakdown:
        if qb.get("skipped") is True:
            continue
        sk = str(qb.get("skill_target", "")).strip().lower()
        sc = qb.get("score")
        if sk and isinstance(sc, (int, float)) and sc < 6.5 and sk not in weak_skill_topics:
            weak_skill_topics[sk] = str(qb.get("question", ""))[:120]

    filler_summary  = final_report.get("filler_word_summary", {})
    posture_summary = final_report.get("posture_summary", {})

    # ── Template recommendations (always built as fallback) ───────────────────
    # Deduplicate: only show unique skill recommendations; group similar ones
    recommendations: List[str] = []
    seen_rec_skills: set = set()
    for sk in weak_areas:
        sk_lower = sk.lower()
        if sk_lower in seen_rec_skills:
            continue
        seen_rec_skills.add(sk_lower)
        topic = weak_skill_topics.get(sk, "")
        # Build a specific recommendation rather than repeating the question
        if expertise_level == "fresher":
            recommendations.append(f"Study {sk} fundamentals: review core concepts, complete a small project, and practise explaining it out loud.")
        elif expertise_level == "intermediate":
            recommendations.append(f"Deepen {sk} knowledge: work through a real-world problem end-to-end and document the trade-offs you considered.")
        else:
            recommendations.append(f"Strengthen {sk} depth: prepare a detailed example covering architecture decisions, performance optimisation, or failure handling.")
    not_assessed_grouped = [sk for sk in not_assessed if sk.lower() not in seen_rec_skills]
    if not_assessed_grouped:
        skills_str = ", ".join(not_assessed_grouped[:4])
        recommendations.append(f"Prepare answers for resume skills not yet assessed: {skills_str}. Use the STAR format for each.")
    if filler_summary.get("total_fillers", 0) > 0:
        common_words = ", ".join([str(i.get("word", "")) for i in filler_summary.get("top_fillers", []) if i.get("word")])
        recommendations.append(
            f"Reduce filler words: {filler_summary.get('total_fillers', 0)} fillers detected"
            + (f" (most common: {common_words})" if common_words else "")
        )
    if posture_summary.get("total_snapshots", 0) > 0:
        recommendations.append(
            f"Posture trend showed {posture_summary.get('most_common_label')}; maintain a more upright and stable posture."
        )
    if not recommendations:
        recommendations.append("Performance is consistent across assessed skills.")

    # ── P2-B: LLM suggestions — replace templates only when non-empty ─────────
    llm_suggestions = _llm_generate_suggestions(
        candidate_name=candidate_name,
        job_role=job_role,
        expertise_level=expertise_level,
        question_breakdown=question_breakdown,
        weak_areas=weak_areas,
        not_assessed=not_assessed,
        skills_analysis=skills_analysis,
    )
    final_recommendations = llm_suggestions if llm_suggestions else recommendations

    reviewer_summary = {
        "overall": (
            "Candidate demonstrates strong depth in selected areas with clear improvement opportunities."
            if final_report.get("needs_human_review")
            else "Candidate performance is consistent and meets expectations."
        ),
        "strengths":      strengths[:8],
        "concerns":       concerns[:8] if concerns else ["No major weak areas among assessed skills."],
        "recommendation": final_recommendations,
    }

    final_score = final_report.get("final_score", 0)
    if final_score >= 8:
        level = "MID-SENIOR"
    elif final_score >= 6.5:
        level = "JUNIOR-MID"
    else:
        level = "ENTRY"

    readiness_index = {
        "level":             level,
        "confidence":        round(min(1.0, final_score / 10), 2),
        "risk":              "HIGH" if final_report.get("needs_human_review") else "LOW",
        "interview_quality": "EXCELLENT" if final_score >= 8 else "GOOD" if final_score >= 6.5 else "WEAK",
    }

    analytics_report = {
        "session_id":        session_id,
        "skills_analysis":   skills_analysis,
        "skill_coverage":    final_report.get("skill_coverage", {}),
        "strengths":         strengths,
        "weak_areas":        weak_areas,
        "not_assessed":      not_assessed,
        "followup_analysis": followup_analysis,
        "answer_quality":    answer_quality,
        "reviewer_summary":  reviewer_summary,
        "readiness_index":   readiness_index,
    }

    out_path = session_dir / "analytics_report.json"
    out_path.write_text(json.dumps(analytics_report, indent=2), encoding="utf-8")

    return {
        "status":          "ok",
        "analytics_path":  str(out_path),
        "readiness_level": readiness_index["level"],
    }
