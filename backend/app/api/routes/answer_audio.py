"""
Audio answer endpoint.
Pipeline: save → rate-limit → Whisper ASR (thread pool, with timeout) → score_text.

Runtime-adaptive ASR:
  GPU mode: whisper-large-v3-turbo — fast, high accuracy (~5–8s for a 60s clip).
  CPU mode: whisper-tiny — lightweight, English-only (~2–8s for a 60s clip).

Audio is always available regardless of GPU. The model tier adapts automatically.
"""

import asyncio
import re
import shutil
import traceback
import uuid
from pathlib import Path

from fastapi import APIRouter, File, HTTPException, UploadFile

from backend.app.core.ml_models import transcribe_audio, is_gpu_available
from backend.app.core.rate_limit import check_rate_limit
from backend.app.core.validation import validate_session_id
from backend.app.core.db_ops import update_session_status
from backend.app.models.session import SessionStatus
from backend.app.api.routes.score_text import score_text_answer

router = APIRouter()

# Timeouts: GPU models are larger but run on accelerator; CPU uses tiny model.
ASR_TIMEOUT_GPU = 120   # seconds — generous for large-v3-turbo on GPU
ASR_TIMEOUT_CPU = 90    # seconds — whisper-tiny on CPU is fast but give headroom


def _storage_dir() -> Path:
    from backend.app.core.storage import get_storage_dir
    return get_storage_dir()


@router.post("/answer/audio")
async def answer_audio(session_id: str, question_id: str, file: UploadFile = File(...)):
    try:
        if not await check_rate_limit(session_id, "answer_audio", max_requests=20, window_seconds=60):
            raise HTTPException(status_code=429, detail="Too many audio submissions. Please slow down.")
        validate_session_id(session_id)

        session_dir = _storage_dir() / session_id
        if not session_dir.exists():
            raise HTTPException(status_code=404, detail="session_id not found")

        # Transition: audio received → answer pending (before ASR)
        await update_session_status(session_id, SessionStatus.ANSWER_PENDING)

        # No GPU check gate — ASR is available on both GPU and CPU now.

        answers_dir = session_dir / "audio"
        answers_dir.mkdir(parents=True, exist_ok=True)

        ext       = Path(file.filename or "audio").suffix or ".webm"
        safe_qid  = re.sub(r"[^a-zA-Z0-9_\-]", "_", question_id)[:60]
        dest_name = f"{safe_qid}_{uuid.uuid4().hex}{ext}"
        dest_path = answers_dir / dest_name

        with dest_path.open("wb") as f:
            shutil.copyfileobj(file.file, f)

        gpu_ok  = is_gpu_available()
        timeout = ASR_TIMEOUT_GPU if gpu_ok else ASR_TIMEOUT_CPU
        try:
            asr_result = await asyncio.wait_for(
                asyncio.to_thread(transcribe_audio, str(dest_path)),
                timeout=timeout,
            )
            transcript = asr_result.get("text", "").strip()
        except asyncio.TimeoutError:
            raise HTTPException(
                status_code=504,
                detail=(
                    f"Audio transcription timed out after {timeout}s. "
                    "Please try a shorter recording or use text answer mode."
                ),
            )
        except Exception as exc:
            print("ASR error:", exc, traceback.format_exc())
            raise HTTPException(status_code=500, detail=f"ASR transcription failed: {str(exc)[:200]}")

        if not transcript:
            raise HTTPException(
                status_code=422,
                detail="Transcription produced empty text. Please speak clearly and re-record.",
            )

        scored = await score_text_answer({
            "session_id":  session_id,
            "question_id": question_id,
            "answer_text": transcript,
        })
        scored["transcript"] = transcript
        scored["audio_path"] = str(dest_path)
        scored["scoring_method"] = "whisper_asr"
        scored["audio_model"] = "whisper-large-v3-turbo" if gpu_ok else "whisper-tiny"
        return scored

    except HTTPException:
        raise
    except Exception as exc:
        print("Error in /answer/audio:", exc, traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"Internal error: {exc}")
