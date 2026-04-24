from pathlib import Path

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from pydantic import BaseModel
from backend.app.core.validation import validate_session_id

router = APIRouter(tags=["Upload"])

MAX_RESUME_SIZE_BYTES = 10 * 1024 * 1024  # 10 MB
ALLOWED_SUFFIXES      = {".pdf", ".docx", ".doc"}


def _storage_dir() -> Path:
    from backend.app.core.storage import get_storage_dir
    return get_storage_dir()


class UploadResponse(BaseModel):
    filename: str
    saved_path: str
    session_id: str


@router.post("/upload/resume", response_model=UploadResponse)
async def upload_resume(session_id: str = Form(...), file: UploadFile = File(...)):
    validate_session_id(session_id)
    base = _storage_dir() / session_id / "resumes"
    if not base.exists():
        raise HTTPException(status_code=404, detail="Session not found. Create a session first.")

    # Sanitise filename — prevent path traversal
    safe_filename = Path(file.filename or "resume").name
    suffix = Path(safe_filename).suffix.lower()
    if suffix not in ALLOWED_SUFFIXES:
        raise HTTPException(
            status_code=415,
            detail=f"Unsupported file type '{suffix}'. Only PDF and DOCX are accepted.",
        )

    out_path = base / safe_filename
    temp_path = base / f".uploading_{safe_filename}"
    size     = 0

    # Stream with size cap — prevents OOM from huge uploads
    with temp_path.open("wb") as f:
        chunk_size = 64 * 1024
        while True:
            chunk = await file.read(chunk_size)
            if not chunk:
                break
            size += len(chunk)
            if size > MAX_RESUME_SIZE_BYTES:
                temp_path.unlink(missing_ok=True)
                raise HTTPException(
                    status_code=413,
                    detail="Resume file too large. Maximum allowed size is 10 MB.",
                )
            f.write(chunk)

    # Keep one authoritative resume per session to avoid parsing stale uploads later.
    for existing in base.iterdir():
        if existing.is_file() and existing != temp_path:
            existing.unlink(missing_ok=True)
    temp_path.replace(out_path)

    return {"filename": safe_filename, "saved_path": str(out_path), "session_id": session_id}
