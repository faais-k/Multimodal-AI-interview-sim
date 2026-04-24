import os

from fastapi import APIRouter
from backend.app.core.database import db_available
from backend.app.core.ml_models import is_gpu_available, get_model_info

router = APIRouter(tags=["Health"])

@router.get("/health")
async def health_check():
    info = get_model_info()
    return {
        "status":           "ok",
        "service":          "backend",
        "stage":            os.getenv("APP_STAGE", "development"),
        "mongodb":          "connected" if db_available() else "disabled (flat-file mode)",
        # ── Runtime capabilities ──────────────────────────────────────────
        "mode":             info["mode"],           # "gpu" | "cpu"
        "gpu":              "available" if is_gpu_available() else "unavailable",
        "embedding_model":  info["embedding_model"],
        "asr_model":        info["asr_model"],
        "asr_available":    info["asr_available"],
        "llm_mode":         info["llm_mode"],       # "local" | "api" | "disabled"
        "llm_model":        info["llm_model"],
        "audio_transcribe": "enabled" if info["asr_available"] else "unavailable (model failed to load)",
    }
