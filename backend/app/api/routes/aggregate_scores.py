import json
import re
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List

from fastapi import APIRouter, HTTPException, Depends
from backend.app.core.db_ops import save_final_report, update_session_status
from backend.app.core.auth import get_optional_user

from backend.app.core.scoring_config import QUESTION_TYPE_WEIGHTS
from backend.app.core.validation import validate_session_id
from backend.app.core.filler_words import aggregate_filler_report

router = APIRouter()

DEFAULT_PASS_THRESHOLD          = 6.0
MIN_COVERAGE_FOR_AUTO_DECISION  = 0.7


def _storage_dir() -> Path:
    from backend.app.core.storage import get_storage_dir
    return get_storage_dir()

def _scores_dir(session_id: str) -> Path:
    return _storage_dir() / session_id / "scores"

def _state_path(session_id: str) -> Path:
    return _storage_dir() / session_id / "interview_state.json"

def _plan_path(session_id: str) -> Path:
    return _storage_dir() / session_id / "interview_plan.json"

def _read_json(p: Path) -> Dict[str, Any]:
    return json.loads(p.read_text(encoding="utf-8"))


def _safe_read_json(p: Path) -> Dict[str, Any]:
    if not p.exists():
        return {}
    try:
        return _read_json(p)
    except Exception:
        return {}


def _safe_read_list(p: Path) -> List[dict]:
    if not p.exists():
        return []
    try:
        data = _read_json(p)
        return data if isinstance(data, list) else []
    except Exception:
        return []


@router.post("/aggregate/{session_id}")
async def aggregate_scores(
    session_id: str, 
    pass_threshold: float = DEFAULT_PASS_THRESHOLD,
    user: dict = Depends(get_optional_user)
):
    validate_session_id(session_id)
    session_dir = _storage_dir() / session_id
    scores_dir  = _scores_dir(session_id)

    if not session_dir.exists():
        raise HTTPException(status_code=404, detail="session not found")
    if not scores_dir.exists():
        raise HTTPException(status_code=404, detail="no scores found for session")

    score_files = list(scores_dir.glob("*.json"))
    if not score_files:
        raise HTTPException(status_code=404, detail="no score files present")

    # Load plan for coverage calculation
    expected_qids: List[str] = []
    plan_questions_map: Dict[str, Dict[str, Any]] = {}
    plan_path = _plan_path(session_id)
    if plan_path.exists():
        plan          = _read_json(plan_path)
        plan_questions = plan.get("questions", [])
        expected_qids = [q.get("id") for q in plan_questions]
        plan_questions_map = {q.get("id"): q for q in plan_questions if q.get("id")}

    scores:                Dict[str, Any]    = {}
    needs_human_questions: List[str]         = []
    per_type:              Dict[str, List[float]] = {}
    total_weighted_sum = 0.0
    total_weight_sum   = 0.0

    for f in score_files:
        try:
            data = _read_json(f)
        except Exception:
            continue

        # question_id is stored inside the file; fall back to filename stem
        qid  = data.get("question_id") or f.stem
        raw  = data.get("raw_score") if data.get("raw_score") is not None else data.get("score")

        qtype = data.get("question_type") or data.get("type") or "technical"
        # Keep behavioral as behavioral, don't map to hr

        weight = data.get("weight")
        if weight is None:
            weight = QUESTION_TYPE_WEIGHTS.get(qtype, {}).get("weight", 0.2)

        similarity   = data.get("similarity")
        needs_review = bool(data.get("needs_human_review", False))

        scores[qid] = {
            "raw_score":          raw,
            "question_type":      qtype,
            "weight":             weight,
            "similarity":         similarity,
            "needs_human_review": needs_review,
            "top_matches":        data.get("top_matches", []),
            "skill_target":       data.get("skill_target", ""),
            "filler_stats":       data.get("filler_stats", {}),
        }

        if needs_review:
            needs_human_questions.append(qid)

        per_type.setdefault(qtype, []).append(raw if raw is not None else 0.0)

        if raw is not None:
            total_weighted_sum += float(raw) * float(weight)
            total_weight_sum   += float(weight)

    # Coverage: plan questions answered / total plan questions
    # Intro/project/wrapup are not in the plan but are always answered —
    # we do not penalise for their presence or absence in coverage.
    expected_count     = len(expected_qids) if expected_qids else None
    answered_plan_qids = [qid for qid in scores if qid in expected_qids]
    answered_plan_count = len(answered_plan_qids)

    coverage_pct = None
    incomplete   = False
    if expected_count:
        coverage_pct = min(1.0, answered_plan_count / expected_count)
        # Only flag incomplete if very few plan questions were actually answered
        if coverage_pct < MIN_COVERAGE_FOR_AUTO_DECISION and answered_plan_count < 2:
            incomplete = True

    final_score = round(total_weighted_sum / total_weight_sum, 2) if total_weight_sum > 0 else 0.0

    per_type_summary = {
        t: {
            "count":     len(vals),
            "avg_raw":   round(sum(vals) / len(vals), 2) if vals else None,
            "total_raw": round(sum(vals), 2),
        }
        for t, vals in per_type.items()
    }

    if incomplete:
        verdict = "INCOMPLETE"
    elif final_score >= pass_threshold and not needs_human_questions:
        verdict = "PASS"
    elif final_score >= pass_threshold:
        verdict = "BORDERLINE"
    else:
        verdict = "FAIL"

    needs_human_overall = verdict in {"BORDERLINE", "FAIL", "INCOMPLETE"}

    parsed_resume = _safe_read_json(session_dir / "parsed_resume.json")
    resume_skills = [str(s).strip() for s in parsed_resume.get("skills", []) if str(s).strip()]
    resume_skills_map = {s.lower(): s for s in resume_skills}

    # total questions answered (from interview_state answers), distinct from scores-count
    state = _safe_read_json(_state_path(session_id))
    answers = state.get("answers", {}) if isinstance(state.get("answers", {}), dict) else {}
    total_questions_answered = len(answers)

    # Skill coverage from skill_target + resume skills
    skill_buckets: Dict[str, List[float]] = {k: [] for k in resume_skills_map.keys()}
    skill_needs_review: Dict[str, int] = {k: 0 for k in resume_skills_map.keys()}
    for qid, data in scores.items():
        target_raw = str(data.get("skill_target", "")).strip()
        if not target_raw:
            continue
        target = target_raw.lower()
        if target not in skill_buckets:
            skill_buckets[target] = []
            skill_needs_review[target] = 0
            if target not in resume_skills_map:
                resume_skills_map[target] = target_raw
        raw = data.get("raw_score")
        if raw is not None:
            skill_buckets[target].append(float(raw))
        if data.get("needs_human_review"):
            skill_needs_review[target] = skill_needs_review.get(target, 0) + 1

    skill_coverage: Dict[str, Dict[str, Any]] = {}
    for sk_l, vals in skill_buckets.items():
        tested = len(vals) > 0
        avg = round(sum(vals) / len(vals), 2) if tested else None
        skill_coverage[sk_l] = {
            "tested": tested,
            "avg_score": avg,
            "questions": len(vals),
            "needs_review": bool(skill_needs_review.get(sk_l, 0)),
            "status": "assessed" if tested else "not_assessed",
        }

    strengths = [k for k, v in skill_coverage.items() if v["tested"] and (v["avg_score"] or 0) >= 7.5]
    weak_areas = [k for k, v in skill_coverage.items() if v["tested"] and (v["avg_score"] or 10) < 6.5]
    not_assessed = [k for k, v in skill_coverage.items() if not v["tested"]]

    # Question breakdown from interview_state answers + plan/state metadata
    questions_asked = state.get("questions_asked", []) if isinstance(state.get("questions_asked"), list) else []
    asked_map = {q.get("id"): q for q in questions_asked if q.get("id")}
    followup_counts: Dict[str, int] = {}
    for qid in answers.keys():
        if str(qid).startswith("followup"):
            target = str((scores.get(qid, {}) or {}).get("skill_target", "")).lower()
            if target:
                followup_counts[target] = followup_counts.get(target, 0) + 1

    question_breakdown: List[Dict[str, Any]] = []
    for qid, ans in answers.items():
        q_text = ans.get("question") or asked_map.get(qid, {}).get("question") or plan_questions_map.get(qid, {}).get("question", "")
        q_type = scores.get(qid, {}).get("question_type") or plan_questions_map.get(qid, {}).get("type", "technical")
        q_skill = (
            scores.get(qid, {}).get("skill_target")
            or asked_map.get(qid, {}).get("skill_target")
            or plan_questions_map.get(qid, {}).get("skill_target", "")
        )
        q_skill_l = str(q_skill).strip().lower()

        # BUG 4 fix: read score file to get llm_evaluation and authoritative raw_score
        safe_qid_breakdown = re.sub(r"[^a-zA-Z0-9_\-]", "_", str(qid))[:80]
        score_path = session_dir / "scores" / f"{safe_qid_breakdown}.json"
        score_data: Dict[str, Any] = {}
        if score_path.exists():
            try:
                score_data = json.loads(score_path.read_text(encoding="utf-8"))
            except Exception:
                pass

        # Prefer raw_score from score file (LLM-adjusted) over the state copy
        q_score = score_data.get("raw_score") or scores.get(qid, {}).get("raw_score") or ans.get("score")

        question_breakdown.append({
            "question":         q_text,
            "question_id":      qid,
            "answer":           ans.get("answer", ""),
            "answer_preview":   str(ans.get("answer", ""))[:120],
            "skill_target":     q_skill_l,
            "score":            q_score,
            "question_type":    q_type,
            "type":             q_type,
            "followups":        0 if str(qid).startswith("followup") else followup_counts.get(q_skill_l, 0),
            # Fields from score file — None when score file missing
            "llm_evaluation":   score_data.get("llm_evaluation"),
            "relevance_check":  score_data.get("relevance_check"),
            "scorer":           score_data.get("scorer", "cosine"),
            "cosine_raw_score": score_data.get("cosine_raw_score"),
        })

    # Posture summary
    posture_dir = session_dir / "posture"
    posture_items = []
    for pf in posture_dir.glob("*.json") if posture_dir.exists() else []:
        data = _safe_read_json(pf)
        if data:
            posture_items.append(data.get("metrics", {}))
    posture_scores = [float(m.get("posture_score", 0.0)) for m in posture_items if m.get("posture_score") is not None]
    labels = [str(m.get("posture_label", "")).strip() for m in posture_items if str(m.get("posture_label", "")).strip()]
    label_counts = Counter(labels)
    posture_summary = {
        "total_snapshots": len(posture_items),
        "good_posture_pct": round((sum(1 for s in posture_scores if s >= 0.7) / len(posture_scores)) * 100, 1) if posture_scores else 0,
        "most_common_label": label_counts.most_common(1)[0][0] if label_counts else None,
        "avg_score": round(sum(posture_scores) / len(posture_scores), 2) if posture_scores else 0.0,
    }

    # Filler summary
    filler_reports = [
        data.get("filler_stats")
        for data in scores.values()
        if isinstance(data.get("filler_stats"), dict)
    ]
    if filler_reports:
        filler_word_summary = aggregate_filler_report(filler_reports)
        filler_word_summary["affected_answers"] = sum(
            1 for r in filler_reports if int(r.get("filler_count", 0) or 0) > 0
        )
    else:
        filler_word_summary = {
            "total_words": 0,
            "total_fillers": 0,
            "overall_ratio": 0.0,
            "avg_fluency_score": 10.0,
            "by_category": {},
            "top_fillers": [],
            "suggestions": [],
            "affected_answers": 0,
        }

    # Violations summary
    violations = _safe_read_list(session_dir / "violations.json")
    by_type = {"WINDOW_BLUR": 0, "TAB_SWITCH": 0, "FULLSCREEN_EXIT": 0}
    for v in violations:
        t = str(v.get("type", "UNKNOWN"))
        by_type[t] = by_type.get(t, 0) + 1
    violations_summary = {
        "total": len(violations),
        "by_type": by_type,
        "flagged": len(violations) >= 12,
    }

    report = {
        "session_id":             session_id,
        "final_score":            final_score,
        "verdict":                verdict,
        "pass_threshold":         pass_threshold,
        "needs_human_review":     needs_human_overall,
        "questions_counted":      len(scores),
        "total_questions_answered": total_questions_answered,
        "expected_questions":     expected_count,
        "coverage_pct":           round(coverage_pct, 2) if coverage_pct is not None else None,
        "incomplete":             incomplete,
        "needs_human_questions":  needs_human_questions,
        "per_type_summary":       per_type_summary,
        "skill_coverage":         skill_coverage,
        "question_breakdown":     question_breakdown,
        "posture_summary":        posture_summary,
        "filler_word_summary":    filler_word_summary,
        "violations_summary":     violations_summary,
        "strengths":              strengths,
        "weak_areas":             weak_areas,
        "not_assessed":           not_assessed,
        "scores":                 scores,
    }

    out_path = session_dir / "final_report.json"
    out_path.write_text(json.dumps(report, indent=2), encoding="utf-8")

    # Persist to MongoDB (non-blocking, non-fatal)
    try:
        analytics_p   = session_dir / "analytics_report.json"
        analytics_doc = {}
        if analytics_p.exists():
            analytics_doc = json.loads(analytics_p.read_text(encoding="utf-8"))
        uid = user.get("uid") if user else None
        await save_final_report(session_id, report, analytics_doc, user_id=uid)
        await update_session_status(
            session_id, "completed",
            {"final_score": report.get("final_score")},
        )
    except Exception as _mongo_err:
        print(f"⚠️  MongoDB report save skipped: {_mongo_err}")

    # Update interview_state (best-effort)
    state_path = _state_path(session_id)
    if state_path.exists():
        try:
            state = _read_json(state_path)
            state.setdefault("meta", {})
            state["meta"]["final_score"]       = final_score
            state["meta"]["final_report_path"] = str(out_path)
            state["completed"]                 = True
            state_path.write_text(json.dumps(state, indent=2), encoding="utf-8")
        except Exception:
            pass

    return {
        "status":             "ok",
        "final_score":        final_score,
        "verdict":            verdict,
        "needs_human_review": needs_human_overall,
        "report_path":        str(out_path),
    }
