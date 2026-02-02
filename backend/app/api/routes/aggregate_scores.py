# backend/app/api/routes/aggregate_scores.py

from fastapi import APIRouter, HTTPException
from pathlib import Path
import json
from typing import Dict, Any, List
from backend.app.core.scoring_config import QUESTION_TYPE_WEIGHTS

router = APIRouter()

DEFAULT_PASS_THRESHOLD = 6.0
MIN_COVERAGE_FOR_AUTO_DECISION = 0.7  # 70% of PLAN questions must be scored


# ───────────────────────────
# Path helpers
# ───────────────────────────

def _base_dir() -> Path:
    return Path(__file__).resolve().parents[5]

def _storage_dir() -> Path:
    return _base_dir() / "storage"

def _scores_dir(session_id: str) -> Path:
    return _storage_dir() / session_id / "scores"

def _state_path(session_id: str) -> Path:
    return _storage_dir() / session_id / "interview_state.json"

def _plan_path(session_id: str) -> Path:
    return _storage_dir() / session_id / "interview_plan.json"

def _read_json(p: Path) -> Dict[str, Any]:
    return json.loads(p.read_text(encoding="utf-8"))


# ───────────────────────────
# Aggregation Endpoint
# ───────────────────────────

@router.post("/aggregate/{session_id}")
async def aggregate_scores(session_id: str, pass_threshold: float = DEFAULT_PASS_THRESHOLD):
    """
    Aggregate all scored answers and generate final_report.json
    """

    storage = _storage_dir()
    session_dir = storage / session_id
    scores_dir = _scores_dir(session_id)

    if not session_dir.exists():
        raise HTTPException(status_code=404, detail="session not found")

    if not scores_dir.exists():
        raise HTTPException(status_code=404, detail="no scores found for session")

    score_files = list(scores_dir.glob("*.json"))
    if not score_files:
        raise HTTPException(status_code=404, detail="no score files present")

    # ── Load interview plan (for coverage)
    expected_qids: List[str] = []
    plan_path = _plan_path(session_id)
    if plan_path.exists():
        plan = _read_json(plan_path)
        expected_qids = [q.get("id") for q in plan.get("questions", [])]

    # ── Aggregation containers
    scores: Dict[str, Any] = {}
    needs_human_questions: List[str] = []
    per_type: Dict[str, List[float]] = {}
    total_weighted_sum = 0.0
    total_weight_sum = 0.0

    # ───────────────────────────
    # Process each score file
    # ───────────────────────────

    for f in score_files:
        try:
            data = _read_json(f)
        except Exception:
            continue

        qid = data.get("question_id") or f.stem
        raw = data.get("raw_score") if data.get("raw_score") is not None else data.get("score")

        qtype = data.get("question_type") or data.get("type") or "technical"
        if qtype == "behavioral":
            qtype = "hr"

        weight = data.get("weight")
        if weight is None:
            weight = QUESTION_TYPE_WEIGHTS.get(qtype, {}).get("weight", 0.2)

        similarity = data.get("similarity")
        needs_review = bool(data.get("needs_human_review", False))

        scores[qid] = {
            "raw_score": raw,
            "question_type": qtype,
            "weight": weight,
            "similarity": similarity,
            "needs_human_review": needs_review,
            "top_matches": data.get("top_matches", [])
        }

        if needs_review:
            needs_human_questions.append(qid)

        per_type.setdefault(qtype, []).append(raw if raw is not None else 0.0)

        if raw is not None:
            total_weighted_sum += float(raw) * float(weight)
            total_weight_sum += float(weight)

    # ───────────────────────────
    # Coverage (PLAN questions only)
    # ───────────────────────────

    expected_count = len(expected_qids) if expected_qids else None
    answered_plan_qids = [qid for qid in scores if qid in expected_qids]
    answered_plan_count = len(answered_plan_qids)

    coverage_pct = None
    incomplete = False
    if expected_count:
        coverage_pct = answered_plan_count / expected_count
        if coverage_pct < MIN_COVERAGE_FOR_AUTO_DECISION:
            incomplete = True

    # ───────────────────────────
    # Final score
    # ───────────────────────────

    final_score = round(total_weighted_sum / total_weight_sum, 2) if total_weight_sum > 0 else 0.0

    # ───────────────────────────
    # Per-type summary
    # ───────────────────────────

    per_type_summary = {
        t: {
            "count": len(vals),
            "avg_raw": round(sum(vals) / len(vals), 2) if vals else None,
            "total_raw": round(sum(vals), 2)
        }
        for t, vals in per_type.items()
    }

    # ───────────────────────────
    # Verdict
    # ───────────────────────────

    if incomplete:
        verdict = "INCOMPLETE"
    elif final_score >= pass_threshold and not needs_human_questions:
        verdict = "PASS"
    elif final_score >= pass_threshold:
        verdict = "BORDERLINE"
    else:
        verdict = "FAIL"

    needs_human_overall = verdict in {"BORDERLINE", "FAIL", "INCOMPLETE"}

    # ───────────────────────────
    # Final report
    # ───────────────────────────

    report = {
        "session_id": session_id,
        "final_score": final_score,
        "verdict": verdict,
        "pass_threshold": pass_threshold,
        "needs_human_review": needs_human_overall,
        "questions_counted": len(scores),
        "expected_questions": expected_count,
        "coverage_pct": round(coverage_pct, 2) if coverage_pct is not None else None,
        "incomplete": incomplete,
        "needs_human_questions": needs_human_questions,
        "per_type_summary": per_type_summary,
        "scores": scores
    }

    out_path = session_dir / "final_report.json"
    out_path.write_text(json.dumps(report, indent=2), encoding="utf-8")

    # ── Update interview_state (best effort)
    state_path = _state_path(session_id)
    if state_path.exists():
        try:
            state = _read_json(state_path)
            state.setdefault("meta", {})
            state["meta"]["final_score"] = final_score
            state["meta"]["final_report_path"] = str(out_path)
            state["completed"] = True
            state_path.write_text(json.dumps(state, indent=2), encoding="utf-8")
        except Exception:
            pass

    return {
        "status": "ok",
        "final_score": final_score,
        "verdict": verdict,
        "needs_human_review": needs_human_overall,
        "report_path": str(out_path)
    }
