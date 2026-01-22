# backend/app/api/routes/posture.py
from fastapi import APIRouter, HTTPException
from pathlib import Path
import json, traceback

router = APIRouter()

@router.post("/posture/report")
async def posture_report(payload: dict):
    """
    Accept posture metrics from client, persist summary and return suggestions.
    payload: {"session_id": "...", "metrics": {...}}
    """
    try:
        session_id = payload.get("session_id")
        metrics = payload.get("metrics", {})
        if not session_id:
            raise HTTPException(status_code=400, detail="session_id required")

        BASE_DIR = Path(__file__).resolve().parents[4]
        STORAGE_DIR = BASE_DIR / "storage"
        session_dir = STORAGE_DIR / session_id
        if not session_dir.exists():
            raise HTTPException(status_code=404, detail="session_id not found")

        # Basic rule-based suggestions
        suggestions = []
        ps = metrics.get("posture_score", 1.0)
        torso = metrics.get("torso_angle", 90)
        shake = metrics.get("hand_shake_score", 0.0)
        hands_visible = metrics.get("hands_visible", True)

        if ps < 0.6:
            suggestions.append("Sit upright: try to keep your back straight and shoulders relaxed.")
        if abs(torso - 90) > 15:
            suggestions.append("Reduce leaning; center your torso facing the camera.")
        if shake and float(shake) > 0.002:
            suggestions.append("Steady your hands: try placing them on the table or use both hands to reduce shaking.")
        if not hands_visible:
            suggestions.append("Keep your hands visible and avoid excessive gestures.")

        # persist a compact posture log
        log_dir = session_dir / "posture"
        log_dir.mkdir(parents=True, exist_ok=True)
        idx = len(list(log_dir.iterdir())) + 1
        # (log_dir / f"{idx}.json").write_text(json.dumps({"metrics": metrics, "suggestions": suggestions}, indent=2))
        # after writing file
        saved_name = f"{idx}.json"
        (log_dir / saved_name).write_text(json.dumps({"metrics": metrics, "suggestions": suggestions}, indent=2))
        return {"status":"ok", "suggestions": suggestions, "saved": True, "log": str(log_dir / saved_name)}

    except HTTPException:
        raise
    except Exception as e:
        print("posture/report error:", e)
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail="Failed to process posture report")
