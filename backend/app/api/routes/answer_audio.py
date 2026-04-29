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
import subprocess
import time
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
ASR_TIMEOUT_GPU = 120  # seconds — generous for large-v3-turbo on GPU
ASR_TIMEOUT_CPU = 90  # seconds — whisper-tiny on CPU is fast but give headroom
MIN_AUDIO_SIZE_BYTES = 512


def _storage_dir() -> Path:
    from backend.app.core.storage import get_storage_dir

    return get_storage_dir()


def _normalise_audio_for_asr(input_path: Path) -> Path:
    """Convert browser audio containers to a 16 kHz mono WAV for Whisper."""
    if not input_path.exists() or input_path.stat().st_size < MIN_AUDIO_SIZE_BYTES:
        raise HTTPException(
            status_code=422,
            detail="Audio file is empty or too short. Please record again.",
        )

    output_path = input_path.with_suffix(".asr.wav")
    cmd = [
        "ffmpeg",
        "-y",
        "-hide_banner",
        "-loglevel",
        "error",
        "-i",
        str(input_path),
        "-ac",
        "1",
        "-ar",
        "16000",
        str(output_path),
    ]
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
    except FileNotFoundError:
        return input_path
    except subprocess.TimeoutExpired:
        raise HTTPException(
            status_code=422,
            detail="Audio conversion timed out. Please try a shorter answer.",
        )

    if result.returncode != 0 or not output_path.exists() or output_path.stat().st_size == 0:
        detail = (result.stderr or "Unsupported or malformed audio").strip()[:300]
        raise HTTPException(
            status_code=422,
            detail=f"Audio could not be decoded. Please re-record and submit again. {detail}",
        )

    return output_path


@router.post("/answer/audio")
async def answer_audio(session_id: str, question_id: str, file: UploadFile = File(...)):
    try:
        if not await check_rate_limit(
            session_id, "answer_audio", max_requests=20, window_seconds=60
        ):
            raise HTTPException(
                status_code=429, detail="Too many audio submissions. Please slow down."
            )
        validate_session_id(session_id)

        session_dir = _storage_dir() / session_id
        if not session_dir.exists():
            raise HTTPException(status_code=404, detail="session_id not found")

        # Transition: audio received → answer pending (before ASR)
        await update_session_status(session_id, SessionStatus.ANSWER_PENDING)

        # No GPU check gate — ASR is available on both GPU and CPU now.

        answers_dir = session_dir / "audio"
        answers_dir.mkdir(parents=True, exist_ok=True)

        ext = Path(file.filename or "audio").suffix or ".webm"
        safe_qid = re.sub(r"[^a-zA-Z0-9_\-]", "_", question_id)[:60]
        dest_name = f"{safe_qid}_{uuid.uuid4().hex}{ext}"
        dest_path = answers_dir / dest_name

        with dest_path.open("wb") as f:
            shutil.copyfileobj(file.file, f)

        asr_path = _normalise_audio_for_asr(dest_path)

        # ── Background Task Migration ──────────────────────────────────────────
        # Instead of blocking the HTTP request for ASR and scoring, we now
        # offload the work to a Celery worker.
        try:
            from backend.app.worker import process_audio_answer_task

            task = process_audio_answer_task.delay(
                session_id=session_id,
                question_id=question_id,
                audio_path=str(asr_path),
            )

            return {
                "status": "accepted",
                "task_id": task.id,
                "message": "Audio answer received. Transcription and scoring started in background.",
            }
        except Exception as e:
            # Fallback to sync mode if Celery/Redis is unavailable
            print(f"⚠️ Celery task failed to enqueue: {e}. Falling back to sync mode.")

            gpu_ok = is_gpu_available()
            timeout = ASR_TIMEOUT_GPU if gpu_ok else ASR_TIMEOUT_CPU

            start_time = time.monotonic()
            asr_result = await asyncio.wait_for(
                asyncio.to_thread(transcribe_audio, str(asr_path)),
                timeout=timeout,
            )
            latency_s = time.monotonic() - start_time

            from backend.app.core.metrics import record_asr_transcription

            record_asr_transcription(outcome="success", latency_s=latency_s)
            transcript = asr_result.get("text", "").strip()

            if not transcript:
                raise HTTPException(
                    status_code=422,
                    detail="Transcription produced empty text. Please speak clearly.",
                )

            scored = await score_text_answer(
                {
                    "session_id": session_id,
                    "question_id": question_id,
                    "answer_text": transcript,
                }
            )
            scored["transcript"] = transcript
            scored["audio_path"] = str(dest_path)
            scored["scoring_method"] = "whisper_asr_sync_fallback"
            return scored

    except HTTPException:
        raise
    except Exception as exc:
        print("Error in /answer/audio:", exc, traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"Internal error: {exc}")
