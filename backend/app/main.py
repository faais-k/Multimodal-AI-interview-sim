from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.app.api.routes.health import router as health_router
from backend.app.api.routes.session import router as session_router
from backend.app.api.routes.upload import router as upload_router
from backend.app.api.routes.answer import router as answer_router
from backend.app.api.routes.parse_resume import router as parse_router
from backend.app.api.routes.interview_plan import router as plan_router
from backend.app.api.routes.score_text import router as score_router
from backend.app.api.routes.answer_audio import router as answer_audio_router
from backend.app.api.routes.posture import router as posture_router


app = FastAPI(
    title="Multimodal AI Interview Simulator",
    version="0.1.0"
)

# CORS (Frontend will connect later)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routes
app.include_router(health_router, prefix="/api")
app.include_router(session_router, prefix="/api")
app.include_router(upload_router, prefix="/api")
app.include_router(answer_router, prefix="/api")
app.include_router(parse_router, prefix="/api")
app.include_router(plan_router, prefix="/api")
app.include_router(score_router, prefix="/api")
app.include_router(answer_audio_router, prefix="/api")
app.include_router(posture_router, prefix="/api")


@app.get("/")
def root():
    return {"message": "AI Interview Backend is running"}
