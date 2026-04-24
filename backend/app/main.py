import logging
import os
import sys
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.app.api.routes.health import router as health_router
from backend.app.api.routes.session import router as session_router
from backend.app.api.routes.session_extra import router as session_extra_router
from backend.app.api.routes.upload import router as upload_router
from backend.app.api.routes.parse_resume import router as parse_router
from backend.app.api.routes.interview_plan import router as plan_router
from backend.app.api.routes.score_text import router as score_router
from backend.app.api.routes.answer_audio import router as answer_audio_router
from backend.app.api.routes.posture import router as posture_router
from backend.app.api.routes.aggregate_scores import router as aggregate_router
from backend.app.api.routes.analytics_report import router as analytics_router
from backend.app.api.routes.final_decision import router as decision_router
from backend.app.api.routes.violation import router as violation_router
from backend.app.api.routes.report import router as report_router
from backend.app.api.routes.cleanup import router as cleanup_router
from backend.app.api.routes.admin import router as admin_router
from backend.app.core.ml_models import load_models
from backend.app.core.database import connect_db, disconnect_db

# ── Logging Configuration ─────────────────────────────────────────────────────
def _setup_logging():
    """Configure structured logging for production."""
    log_level = os.getenv("LOG_LEVEL", "INFO").upper()
    
    # Configure root logger
    logging.basicConfig(
        level=getattr(logging, log_level, logging.INFO),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[
            logging.StreamHandler(sys.stdout)
        ]
    )
    
    # Set specific levels for noisy libraries
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("motor").setLevel(logging.WARNING)
    
    return logging.getLogger(__name__)

logger = _setup_logging()


def get_cors_origins() -> list:
    """
    Get CORS allowed origins from environment variable.

    Set ALLOWED_ORIGINS to a comma-separated list of exact origin URLs.
    Example: ALLOWED_ORIGINS=https://my-app.vercel.app,https://my-space.hf.space

    NOTE: FastAPI CORSMiddleware does NOT support wildcard patterns
    like https://*.vercel.app — only exact strings or a single "*".
    """
    env_origins = os.getenv("ALLOWED_ORIGINS", "").strip()

    if env_origins:
        origins = [o.strip() for o in env_origins.split(",") if o.strip()]
        if origins:
            return origins

    # No explicit config — allow all origins but warn in production
    app_stage = os.getenv("APP_STAGE", "development").lower()
    if app_stage == "production":
        logger.warning(
            "ALLOWED_ORIGINS is not set. Defaulting to allow all origins. "
            "Set ALLOWED_ORIGINS=https://your-frontend.vercel.app for production."
        )
    return ["*"]


def _verify_spacy_model():
    """Verify that the required spacy model is available for resume parsing."""
    try:
        import spacy
        try:
            spacy.load("en_core_web_sm")
            logger.info("Spacy model 'en_core_web_sm' verified.")
            return True
        except OSError:
            logger.warning(
                "Spacy model 'en_core_web_sm' not found. "
                "Resume parsing will have reduced accuracy. "
                "Install with: python -m spacy download en_core_web_sm"
            )
            return False
    except ImportError:
        logger.warning("Spacy not installed. Resume parsing will fail.")
        return False


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting: pre-loading ML models...")
    load_models()
    logger.info("ML models ready.")
    
    # Verify spacy model for resume parsing
    _verify_spacy_model()
    
    await connect_db()
    logger.info("Database connection established (or running in flat-file mode).")

    try:
        from backend.app.api.routes.cleanup import cleanup_old_sessions

        result = await cleanup_old_sessions(max_age_hours=48, enforce_auth=False)
        logger.info(
            f"Startup cleanup: deleted {result['deleted']} old sessions, "
            f"skipped {result['skipped']}"
        )
    except Exception as e:
        logger.warning(f"Startup cleanup failed (non-fatal): {e}")

    logger.info("Application startup complete. Ready to accept requests.")
    
    yield
    
    await disconnect_db()
    logger.info("Application shutting down.")


app = FastAPI(
    title="Ascent - AI Interview Simulator",
    version="1.0.0",
    description=(
        "Resume-aware, proctored AI interview system. "
        "Hybrid LLM + cosine similarity scoring. Qwen2.5-7B evaluation engine."
    ),
    lifespan=lifespan,
)

cors_origins = get_cors_origins()
logger.info(f"CORS configured with {len(cors_origins)} allowed origins")

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health_router, prefix="/api")
app.include_router(session_router, prefix="/api")
app.include_router(session_extra_router, prefix="/api")
app.include_router(upload_router, prefix="/api")
app.include_router(parse_router, prefix="/api")
app.include_router(plan_router, prefix="/api")
app.include_router(score_router, prefix="/api")
app.include_router(answer_audio_router, prefix="/api")
app.include_router(posture_router, prefix="/api")
app.include_router(aggregate_router, prefix="/api")
app.include_router(analytics_router, prefix="/api")
app.include_router(decision_router, prefix="/api")
app.include_router(violation_router, prefix="/api")
app.include_router(report_router, prefix="/api")
app.include_router(cleanup_router, prefix="/api")
app.include_router(admin_router, prefix="/api")


@app.get("/")
def root():
    return {
        "message": "Ascent - AI Interview Simulator Backend v1.0.0",
        "docs": "/docs",
        "health": "/api/health",
    }
