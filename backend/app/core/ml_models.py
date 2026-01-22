"""
Centralized ML model loading and inference utilities.
All heavy models are loaded once and reused across requests.

This file is intentionally defensive:
- load_models() is used by FastAPI lifespan if available.
- get_sentence_transformer() will lazy-load on first call if necessary,
  so endpoints still work if lifespan didn't run for some reason.
"""

import threading
from typing import Union, List, Any, Optional

# keep name small and explicit
_SENTENCE_MODEL_NAME = "all-MiniLM-L6-v2"

_sentence_model: Optional[Any] = None
_sentence_lock = threading.Lock()


def load_models():
    """
    Load all ML models at application startup.
    Safe to call multiple times (idempotent).
    """
    global _sentence_model
    if _sentence_model is None:
        with _sentence_lock:
            if _sentence_model is None:
                # Import inside function to avoid heavy imports at module import time
                print("📥 Loading SentenceTransformer (this may take a moment)...")
                from sentence_transformers import SentenceTransformer
                _sentence_model = SentenceTransformer(_SENTENCE_MODEL_NAME)
                print("✅ SentenceTransformer loaded")


def get_sentence_transformer():
    """
    Return the cached SentenceTransformer.
    If it isn't loaded yet, call load_models() to lazy-load it (safe fallback).
    This keeps endpoints resilient to startup lifecycle edge-cases.
    """
    global _sentence_model
    if _sentence_model is None:
        # Lazy-load as a fallback. This call is thread-safe due to the lock in load_models().
        load_models()
    return _sentence_model


def encode_sentence(texts: Union[str, List[str]], convert_to_tensor: bool = True):
    """
    Encode text(s) into embeddings using the shared SentenceTransformer.
    This will lazy-load the model if necessary.
    """
    model = get_sentence_transformer()
    return model.encode(texts, convert_to_tensor=convert_to_tensor)
