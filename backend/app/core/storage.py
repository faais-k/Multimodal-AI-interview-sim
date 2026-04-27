"""
Centralised storage path resolution.

STORAGE_DIR env var overrides the default relative path.
This allows Docker/HF Space deployments to point storage at a custom directory.
"""
import json
import os
import tempfile
from pathlib import Path
from typing import Any, Dict


def get_storage_dir() -> Path:
    """Return the root storage directory.

    Priority:
      1. STORAGE_DIR environment variable (set in HF Space, .env, or Docker)
      2. <repo_root>/storage  (default for local dev)
    """
    env_path = os.getenv("STORAGE_DIR", "").strip()
    if env_path:
        p = Path(env_path)
        p.mkdir(parents=True, exist_ok=True)
        return p
    # Resolve from this file's location: backend/app/core/ → 3 levels up → repo root
    return Path(__file__).resolve().parents[3] / "storage"


def write_json_atomic(path: Path, data: Dict[str, Any], indent: int = 2) -> None:
    """Atomically write JSON data to a file using temp file + rename.

    This ensures that even if the process crashes or disk is full during write,
    the existing file remains intact. The temp file is created in the same
    directory as the target file to ensure atomic rename works across filesystems.

    Args:
        path: Target file path
        data: Dictionary to serialize as JSON
        indent: JSON indentation level (default: 2)
    """
    # Ensure parent directory exists
    path.parent.mkdir(parents=True, exist_ok=True)

    # Create temp file in same directory for atomic rename
    fd, temp_path = tempfile.mkstemp(
        dir=path.parent,
        prefix=f".{path.stem}_",
        suffix=".tmp"
    )
    try:
        # Write JSON to temp file
        with os.fdopen(fd, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=indent, ensure_ascii=False)

        # Atomic rename (POSIX guarantees atomicity within same filesystem)
        os.replace(temp_path, path)
    except Exception:
        # Clean up temp file on any error
        try:
            os.unlink(temp_path)
        except OSError:
            pass
        raise
