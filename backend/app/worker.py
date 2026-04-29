import os
import time
import logging
import asyncio
import traceback
from celery import Celery
from pathlib import Path

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Redis configuration
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

# Initialize Celery
app = Celery(
    "interview_worker",
    broker=REDIS_URL,
    backend=REDIS_URL
)

# Celery configuration
app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=300,  # 5 minutes max per task
)

@app.task(name="process_audio_answer")
def process_audio_answer_task(session_id: str, question_id: str, audio_path: str):
    """Background task to transcribe and score an audio answer."""
    from backend.app.core.ml_models import transcribe_audio
    from backend.app.api.routes.score_text import score_text_answer
    from backend.app.core.metrics import record_asr_transcription
    
    logger.info(f"Processing audio answer for session {session_id}, question {question_id}")
    
    try:
        # 1. Transcription
        start_time = time.monotonic()
        asr_result = transcribe_audio(audio_path)
        latency_s = time.monotonic() - start_time
        record_asr_transcription(outcome="success", latency_s=latency_s)
        
        transcript = asr_result.get("text", "").strip()
        if not transcript:
            return {"status": "error", "message": "Transcription produced empty text"}
            
        # 2. Scoring
        # We need an event loop to run the async score_text_answer
        loop = asyncio.get_event_loop()
        scored = loop.run_until_complete(score_text_answer({
            "session_id": session_id,
            "question_id": question_id,
            "answer_text": transcript
        }))
        
        scored["transcript"] = transcript
        scored["audio_path"] = audio_path
        scored["scoring_method"] = "whisper_asr_background"
        
        return {"status": "ok", "result": scored}
        
    except Exception as e:
        logger.error(f"Error in process_audio_answer_task: {e}\n{traceback.format_exc()}")
        record_asr_transcription(outcome="error", latency_s=0.0)
        return {"status": "error", "message": str(e)}

@app.task(name="score_text_answer")
def score_text_answer_task(session_id: str, question_id: str, answer_text: str):
    """Background task to score a text answer."""
    from backend.app.api.routes.score_text import score_text_answer
    
    logger.info(f"Scoring text answer for session {session_id}, question {question_id}")
    
    try:
        loop = asyncio.get_event_loop()
        scored = loop.run_until_complete(score_text_answer({
            "session_id": session_id,
            "question_id": question_id,
            "answer_text": answer_text
        }))
        
        return {"status": "ok", "result": scored}
        
    except Exception as e:
        logger.error(f"Error in score_text_answer_task: {e}\n{traceback.format_exc()}")
        return {"status": "error", "message": str(e)}

@app.task(name="generate_dynamic_interview")
def generate_dynamic_interview_task(session_id: str):
    """Background task to generate dynamic interview questions."""
    from backend.app.api.routes.dynamic_interview import generate_dynamic_interview_logic
    
    logger.info(f"Generating dynamic interview for session {session_id}")
    
    try:
        loop = asyncio.get_event_loop()
        result = loop.run_until_complete(generate_dynamic_interview_logic(session_id))
        return {"status": "ok", "result": result}
    except Exception as e:
        logger.error(f"Error in generate_dynamic_interview_task: {e}\n{traceback.format_exc()}")
        return {"status": "error", "message": str(e)}

@app.task(name="parse_and_extract_resume")
def parse_and_extract_resume_task(session_id: str, file_path_str: str, filename: str):
    """Background task to parse and extract resume data."""
    from backend.app.api.routes.parse_and_extract import parse_and_extract_logic
    
    logger.info(f"Parsing resume for session {session_id}")
    
    try:
        file_path = Path(file_path_str)
        loop = asyncio.get_event_loop()
        result = loop.run_until_complete(parse_and_extract_logic(session_id, file_path, filename))
        return {"status": "ok", "result": result}
    except Exception as e:
        logger.error(f"Error in parse_and_extract_resume_task: {e}\n{traceback.format_exc()}")
        return {"status": "error", "message": str(e)}
