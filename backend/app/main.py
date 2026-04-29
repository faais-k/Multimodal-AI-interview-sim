import logging
import os
import sys
import uuid
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from backend.app.api.routes.health import router as health_router
from backend.app.api.routes.session import router as session_router
from backend.app.api.routes.session_extra import router as session_extra_router
from backend.app.api.routes.upload import router as upload_router
from backend.app.api.routes.parse_resume import router as parse_router
from backend.app.api.routes.parse_and_extract import router as parse_extract_router
from backend.app.api.routes.interview_plan import router as plan_router
from backend.app.api.routes.dynamic_interview import router as dynamic_interview_router
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
from backend.app.api.routes.user import router as user_router
from backend.app.api.routes.metrics_route import router as metrics_router
from backend.app.core.ml_models import load_models
from backend.app.core.database import connect_db, disconnect_db
from backend.app.core.auth import init_firebase


# ── Logging Configuration ─────────────────────────────────────────────────────
def _setup_logging():
    """Configure structured logging for production."""
    log_level = os.getenv("LOG_LEVEL", "INFO").upper()

    # Configure root logger
    logging.basicConfig(
        level=getattr(logging, log_level, logging.INFO),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[logging.StreamHandler(sys.stdout)],
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
        logger.error(
            "ALLOWED_ORIGINS is not set in PRODUCTION. Refusing all origins for safety. "
            "Set ALLOWED_ORIGINS=https://your-frontend.vercel.app"
        )
        return []

    logger.warning("No ALLOWED_ORIGINS set. Defaulting to allow all origins in development.")
    return ["*"]


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting: pre-loading ML models...")
    load_models()
    logger.info("ML models ready.")

    await connect_db()
    logger.info("Database connection established (or running in flat-file mode).")

    init_firebase()

    # ── Diagnostic Route Logging ──────────────────────────────────────────
    logger.info("Listing all registered routes:")
    for route in app.routes:
        methods = getattr(route, "methods", ["GET"])
        logger.info(f"Route: {route.path} | Methods: {list(methods)}")
    # ──────────────────────────────────────────────────────────────────────

    try:
        from backend.app.api.routes.cleanup import cleanup_old_sessions

        result = await cleanup_old_sessions(max_age_hours=48, internal=True)
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


# ── TR-1: Request ID & Metrics middleware for production tracing ─────────────────────────
@app.middleware("http")
async def add_request_id_and_metrics(request: Request, call_next):
    import time
    from backend.app.core.metrics import record_request

    request_id = str(uuid.uuid4())
    request.state.request_id = request_id

    start_time = time.monotonic()
    try:
        response = await call_next(request)
        status_code = response.status_code
    except Exception as e:
        status_code = 500
        raise e
    finally:
        duration_s = time.monotonic() - start_time
        record_request(
            method=request.method,
            endpoint=request.url.path,
            status_code=status_code,
            duration_s=duration_s,
        )

    response.headers["X-Request-ID"] = request_id
    return response


app.include_router(health_router, prefix="/api")
app.include_router(session_router, prefix="/api")
app.include_router(session_extra_router, prefix="/api")
app.include_router(upload_router, prefix="/api")
app.include_router(parse_router, prefix="/api")
app.include_router(parse_extract_router, prefix="/api")
app.include_router(plan_router, prefix="/api")
app.include_router(dynamic_interview_router, prefix="/api")
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
app.include_router(user_router, prefix="/api/user", tags=["User"])
app.include_router(metrics_router, prefix="/api")


@app.get("/")
def root():
    return {
        "message": "Ascent - AI Interview Simulator Backend v1.0.0",
        "docs": "/docs",
        "health": "/api/health",
    }
