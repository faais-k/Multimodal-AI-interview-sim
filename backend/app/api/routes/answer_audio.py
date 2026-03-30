"""
Audio answer endpoint.
Pipeline: save → rate-limit check → Whisper ASR (thread pool) → score_text → return all.

Whisper inference runs in asyncio.to_thread() to avoid blocking the event loop.
"""

import asyncio
import re
import shutil
import traceback
import uuid
from pathlib import Path

from fastapi import APIRouter, File, HTTPException, UploadFile

from backend.app.core.ml_models import transcribe_audio
from backend.app.core.rate_limit import check_rate_limit
from backend.app.core.validation import validate_session_id
from backend.app.api.routes.score_text import score_text_answer

router = APIRouter()


def _storage_dir() -> Path:
    return Path(__file__).resolve().parents[4] / "storage"


@router.post("/answer/audio")
async def answer_audio(session_id: str, question_id: str, file: UploadFile = File(...)):
    try:
        # P4-C: Rate limit — first check before any work
        if not await check_rate_limit(session_id, "answer_audio", max_requests=20, window_seconds=60):
            raise HTTPException(status_code=429, detail="Too many audio submissions. Please slow down.")
        # BUG 3: Validate session_id is a UUID4 before any file I/O
        validate_session_id(session_id)

        session_dir = _storage_dir() / session_id
        if not session_dir.exists():
            raise HTTPException(status_code=404, detail="session_id not found")

        # Save audio — sanitise question_id in filename
        answers_dir = session_dir / "audio"
        answers_dir.mkdir(parents=True, exist_ok=True)

        ext       = Path(file.filename or "audio").suffix or ".webm"
        safe_qid  = re.sub(r"[^a-zA-Z0-9_\-]", "_", question_id)[:60]
        dest_name = f"{safe_qid}_{uuid.uuid4().hex}{ext}"
        dest_path = answers_dir / dest_name

        with dest_path.open("wb") as f:
            shutil.copyfileobj(file.file, f)

        # Transcribe — run synchronous Whisper in a thread
        try:
            asr_result = await asyncio.to_thread(transcribe_audio, str(dest_path))
            transcript = asr_result.get("text", "").strip()
        except Exception as exc:
            print("ASR error:", exc, traceback.format_exc())
            raise HTTPException(
                status_code=500,
                detail=f"ASR transcription failed: {str(exc)[:200]}",
            )

        if not transcript:
            raise HTTPException(
                status_code=422,
                detail="Transcription produced empty text. Please speak clearly and re-record.",
            )

        # Score via the text scoring pipeline (includes LLM evaluation + filler analysis)
        scored = await score_text_answer({
            "session_id":  session_id,
            "question_id": question_id,
            "answer_text": transcript,
        })

        scored["transcript"] = transcript
        scored["audio_path"] = str(dest_path)
        return scored

    except HTTPException:
        raise
    except Exception as exc:
        print("Error in /answer/audio:", exc, traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"Internal error: {exc}")
