from fastapi import APIRouter, Depends
from typing import List, Dict, Any
from backend.app.core.auth import get_current_user
from backend.app.core.database import db_available, get_db

router = APIRouter()

@router.get("/history")
async def get_user_history(user: dict = Depends(get_current_user)) -> Dict[str, Any]:
    """Retrieve all past interview reports for the authenticated user."""
    if not db_available():
        return {"status": "ok", "history": []}
        
    db = get_db()
    uid = user.get("uid")
    
    try:
        # Fetch reports associated with the user
        cursor = db.reports.find(
            {"user_id": uid}, 
            {"_id": 0}
        ).sort("saved_at", -1).limit(50)
        
        reports = await cursor.to_list(length=50)
        return {"status": "ok", "history": reports}
    except Exception as e:
        return {"status": "error", "detail": str(e), "history": []}
