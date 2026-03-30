from fastapi import APIRouter
from backend.app.core.database import db_available

router = APIRouter(tags=["Health"])

@router.get("/health")
async def health_check():
    return {
        "status":  "ok",
        "service": "backend",
        "stage":   "development",
        "mongodb": "connected" if db_available() else "disabled (flat-file mode)",
    }
