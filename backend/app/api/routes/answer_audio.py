"""
Audio answer endpoint.
Pipeline: save → rate-limit → Whisper ASR (thread pool, with timeout) → score_text.

CPU MODE WARNING: Whisper large-v3-turbo is a large model. On CPU it can take
5-20+ minutes for a short clip, or may time out entirely. When running on CPU,
a clear error is returned immediately rather than hanging indefinitely.
GPU (Colab T4) is strongly recommended for audio answers.
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
from backend.app.api.routes.score_text import score_text_answer

router = APIRouter()

# On CPU, audio transcription will almost certainly time out or take unacceptably long.
# We enforce a hard cap; on GPU (Colab T4) 9s of audio completes in ~5–8s.
ASR_TIMEOUT_GPU = 120   # seconds — generous for Colab T4
ASR_TIMEOUT_CPU = 30    # seconds — enough for tiny-model fallback; fails fast otherwise


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

        # Check GPU availability early — give CPU users a fast, clear error
        gpu_ok = is_gpu_available()
        if not gpu_ok:
            raise HTTPException(
                status_code=503,
                detail=(
                    "Audio transcription requires a GPU-backed backend. This deployment is running on CPU. "
                    "Please switch to text answer mode, or deploy the backend on GPU-enabled infrastructure."
                ),
            )

        answers_dir = session_dir / "audio"
        answers_dir.mkdir(parents=True, exist_ok=True)

        ext       = Path(file.filename or "audio").suffix or ".webm"
        safe_qid  = re.sub(r"[^a-zA-Z0-9_\-]", "_", question_id)[:60]
        dest_name = f"{safe_qid}_{uuid.uuid4().hex}{ext}"
        dest_path = answers_dir / dest_name

        with dest_path.open("wb") as f:
            shutil.copyfileobj(file.file, f)

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
        return scored

    except HTTPException:
        raise
    except Exception as exc:
        print("Error in /answer/audio:", exc, traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"Internal error: {exc}")
