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


@asynccontextmanager
async def lifespan(app: FastAPI):
    print("Starting: pre-loading ML models...")
    load_models()
    print("Models ready.")
    await connect_db()

    try:
        from backend.app.api.routes.cleanup import cleanup_old_sessions

        result = await cleanup_old_sessions(max_age_hours=48, enforce_auth=False)
        print(
            f"Startup cleanup: deleted {result['deleted']} old sessions, "
            f"skipped {result['skipped']}"
        )
    except Exception as e:
        print(f"Startup cleanup failed (non-fatal): {e}")

    yield
    await disconnect_db()
    print("Shutting down.")


app = FastAPI(
    title="Ascent - AI Interview Simulator",
    version="1.0.0",
    description=(
        "Resume-aware, proctored AI interview system. "
        "Hybrid LLM + cosine similarity scoring. Qwen2.5-7B evaluation engine."
    ),
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
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
