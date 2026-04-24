"""
Centralised storage path resolution.

STORAGE_DIR env var overrides the default relative path.
This allows Docker/HF Space deployments to point storage at a custom directory.
"""
import os
from pathlib import Path


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
