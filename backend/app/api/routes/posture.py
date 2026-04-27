import json
import traceback
import uuid
from pathlib import Path

from fastapi import APIRouter, HTTPException

from backend.app.core.storage import get_storage_dir
from backend.app.core.validation import validate_session_id

router = APIRouter()


def _storage_dir() -> Path:
    return get_storage_dir()


@router.post("/posture/report")
async def posture_report(payload: dict):
    """
    Accept posture metrics from client, persist and return suggestions.
    payload: {"session_id": "...", "metrics": {...}}
    """
    try:
        session_id = payload.get("session_id")
        metrics    = payload.get("metrics", {})
        if not session_id:
            raise HTTPException(status_code=400, detail="session_id required")
        validate_session_id(session_id)

        session_dir = _storage_dir() / session_id
        if not session_dir.exists():
            raise HTTPException(status_code=404, detail="session_id not found")

        suggestions = []
        ps            = float(metrics.get("posture_score", 1.0))
        torso         = float(metrics.get("spine_height",  90))
        shake         = float(metrics.get("hand_shake_score", 0.0))
        hands_visible = metrics.get("hands_visible", True)

        if ps < 0.6:
            suggestions.append("Sit upright — keep your back straight and shoulders relaxed.")
        # torso_angle is now a normalized spine height value (0–40 typical),
        # NOT degrees. Values below 10 indicate slouching.
        if torso < 10:
            suggestions.append("Sit up straighter — your spine appears compressed. Try to lengthen your torso.")
        if shake > 0.002:
            suggestions.append("Steady your hands — place them on the desk or in your lap.")
        if not hands_visible:
            suggestions.append("Keep your hands visible; avoid excessive gestures.")

        log_dir = session_dir / "posture"
        log_dir.mkdir(parents=True, exist_ok=True)

        # Use uuid for filename — avoids race condition from iterdir() counting
        saved_name = f"{uuid.uuid4().hex}.json"
        (log_dir / saved_name).write_text(
            json.dumps({"metrics": metrics, "suggestions": suggestions}, indent=2)
        )

        return {"status": "ok", "suggestions": suggestions, "saved": True}

    except HTTPException:
        raise
    except Exception as exc:
        print("posture/report error:", exc, traceback.format_exc())
        raise HTTPException(status_code=500, detail="Failed to process posture report")
