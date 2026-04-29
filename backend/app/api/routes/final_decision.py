from fastapi import APIRouter, HTTPException
from pathlib import Path
import json
from typing import Dict, Any, List

from backend.app.core.storage import get_storage_dir
from backend.app.core.validation import validate_session_id

router = APIRouter()

# -----------------------------
# Helpers
# -----------------------------


def _base_dir() -> Path:
    return Path(__file__).resolve().parents[4]


def _storage_dir() -> Path:
    return get_storage_dir()


def _read_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _clamp(val: float, lo: float, hi: float):
    return max(lo, min(val, hi))


# -----------------------------
# Final Decision Engine
# -----------------------------


@router.post("/decision/{session_id}")
async def final_decision(session_id: str):
    validate_session_id(session_id)
    session_dir = _storage_dir() / session_id

    if not session_dir.exists():
        raise HTTPException(status_code=404, detail="session not found")

    final_report_path = session_dir / "final_report.json"
    analytics_path = session_dir / "analytics_report.json"

    if not final_report_path.exists() or not analytics_path.exists():
        raise HTTPException(status_code=404, detail="required reports missing")

    final_report = _read_json(final_report_path)
    analytics = _read_json(analytics_path)

    final_score = final_report.get("final_score", 0)
    needs_human = final_report.get("needs_human_review", False)
    consistency = analytics.get("answer_quality", {}).get("consistency")
    readiness = analytics.get("readiness_index", {}).get("level")

    # Count HIGH risk skills
    high_risk_skills = [
        skill
        for skill, data in analytics.get("skills_analysis", {}).items()
        if data.get("risk") == "HIGH"
    ]

    reasons: List[str] = []

    # -----------------------------
    # Decision Logic
    # -----------------------------

    if final_score < 6.0:
        decision = "FAIL"
        reasons.append("Overall score below minimum threshold")

    elif final_score >= 7.5 and consistency != "LOW" and not high_risk_skills:
        decision = "PASS"
        reasons.append("Strong overall performance with consistent answers")

    else:
        decision = "BORDERLINE"
        reasons.append("Mixed signals across scoring and depth")

    if needs_human:
        reasons.append("Human review flagged during evaluation")

    if consistency == "LOW":
        reasons.append("Inconsistent answer depth detected")

    if high_risk_skills:
        reasons.append(f"High-risk skills identified: {', '.join(high_risk_skills[:3])}")

    confidence = round(_clamp(final_score / 10, 0.0, 1.0), 2)

    decision_report = {
        "session_id": session_id,
        "decision": decision,
        "confidence": confidence,
        "final_score": final_score,
        "readiness_level": readiness,
        "needs_human_review": needs_human,
        "reasons": reasons,
    }

    out_path = session_dir / "final_decision.json"
    out_path.write_text(json.dumps(decision_report, indent=2), encoding="utf-8")

    return {
        "status": "ok",
        "decision": decision,
        "confidence": confidence,
        "decision_path": str(out_path),
    }
