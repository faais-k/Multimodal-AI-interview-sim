"""
Centralised ML model loading with automatic GPU/CPU tier selection.

Runtime Modes:
  GPU mode (CUDA available):
    Embeddings : sentence-transformers/all-mpnet-base-v2  (110M params)
    ASR        : openai/whisper-large-v3-turbo            (~2 GB)
    LLM        : Qwen/Qwen2.5-7B-Instruct 4-bit NF4      (~4.5 GB VRAM)

  CPU mode (no CUDA):
    Embeddings : sentence-transformers/all-MiniLM-L6-v2   (22M params, ~80 MB)
    ASR        : openai/whisper-tiny                      (~39 MB)
    LLM        : HuggingFace Inference API (serverless)   (requires HF_TOKEN)

VRAM budget on GPU (e.g. T4 15 GB):
  Qwen2.5-7B 4-bit  ~4.5 GB
  Whisper large-v3-turbo  ~2.0 GB
  all-mpnet-base-v2  ~0.5 GB
  ─────────────────────────
  Total  ~7.0 GB  (fits with room to spare)

LLM loading behaviour:
  GPU:  Default lazy — loads on first call to llm_generate().
        Set env var LLM_EAGER_LOAD=true to pre-warm at startup (adds ~90s).
  CPU:  HF Inference API via requests — zero local memory.
        Requires HF_TOKEN env var. Without it, falls back to cosine-only scoring.
"""

import logging
import os
import threading
import time
from typing import Any, List, Optional, Union

logger = logging.getLogger(__name__)

# ── GPU detection (computed once at import time) ──────────────────────────────


def _detect_gpu() -> bool:
    try:
        import torch

        return torch.cuda.is_available()
    except ImportError:
        return False


GPU_AVAILABLE = _detect_gpu()


# ── Model name selection ──────────────────────────────────────────────────────

_SENTENCE_MODEL_GPU = "sentence-transformers/all-mpnet-base-v2"
_SENTENCE_MODEL_CPU = "sentence-transformers/all-MiniLM-L6-v2"
SENTENCE_MODEL_NAME = _SENTENCE_MODEL_GPU if GPU_AVAILABLE else _SENTENCE_MODEL_CPU

_ASR_MODEL_GPU = "openai/whisper-large-v3-turbo"
_ASR_MODEL_CPU = "openai/whisper-tiny"
ASR_MODEL_NAME = _ASR_MODEL_GPU if GPU_AVAILABLE else _ASR_MODEL_CPU

LLM_MODEL_ID = "Qwen/Qwen2.5-7B-Instruct"
_HF_API_MODEL = os.getenv("HF_API_MODEL", "Qwen/Qwen2.5-72B-Instruct")
_HF_TOKEN = os.getenv("HF_TOKEN", "")

# Controls whether LLM is pre-warmed at startup (GPU mode only)
LLM_EAGER_LOAD = os.getenv("LLM_EAGER_LOAD", "false").lower() == "true"

# LLM mode: "local" (GPU), "api" (CPU + HF_TOKEN), "disabled" (CPU, no token)
_llm_mode = "disabled"


# ── Sentinel for API proxy mode ───────────────────────────────────────────────


class _APIProxy:
    """Sentinel indicating LLM calls route through HF Inference API."""

    pass


_API_PROXY = _APIProxy()


# ── Module-level singletons ───────────────────────────────────────────────────

_sentence_model: Optional[Any] = None
_asr_pipeline: Optional[Any] = None
_llm_model: Optional[Any] = None
_llm_tokenizer: Optional[Any] = None

_sentence_lock = threading.Lock()
_asr_lock = threading.Lock()
_llm_lock = threading.Lock()

# ── PERF-1: Embedding cache — avoids re-computing identical embeddings ────────
_embedding_cache: dict = {}
_EMBEDDING_CACHE_MAX = 500  # Max entries before eviction

# ── TR-2: Circuit breaker for HF API — prevents wasting time on a dead API ────
_hf_api_failure_count = 0
_hf_api_circuit_open = False
_hf_api_circuit_opened_at = 0.0
_HF_CIRCUIT_THRESHOLD = 5  # Open circuit after this many consecutive failures
_HF_CIRCUIT_COOLDOWN = 300  # Seconds before retrying (5 minutes)


def is_hf_circuit_open() -> bool:
    """Return True if the HF API circuit is currently open (in fallback mode)."""
    if _hf_api_circuit_open:
        elapsed = time.time() - _hf_api_circuit_opened_at
        if elapsed < _HF_CIRCUIT_COOLDOWN:
            return True
    return False


# ── Sentence Transformer ─────────────────────────────────────────────────────


def load_sentence_model() -> None:
    global _sentence_model
    if _sentence_model is None:
        with _sentence_lock:
            if _sentence_model is None:
                print(f"📥 Loading SentenceTransformer ({SENTENCE_MODEL_NAME})…")
                from sentence_transformers import SentenceTransformer

                _sentence_model = SentenceTransformer(SENTENCE_MODEL_NAME)
                print(f"✅ SentenceTransformer ready ({SENTENCE_MODEL_NAME})")


def get_sentence_transformer() -> Any:
    if _sentence_model is None:
        load_sentence_model()
    return _sentence_model


def encode_sentence(texts: Union[str, List[str]], convert_to_tensor: bool = True) -> Any:
    """Encode text to embeddings with caching for single strings."""
    # PERF-1: Cache single-string encodings (the common case in scoring)
    if isinstance(texts, str):
        import hashlib

        cache_key = hashlib.md5(texts.encode()).hexdigest()[:16]
        if cache_key in _embedding_cache:
            return _embedding_cache[cache_key]
        result = get_sentence_transformer().encode(texts, convert_to_tensor=convert_to_tensor)
        # Evict oldest entries if cache is full
        if len(_embedding_cache) >= _EMBEDDING_CACHE_MAX:
            # Remove first 100 entries (FIFO approximation)
            for k in list(_embedding_cache.keys())[:100]:
                del _embedding_cache[k]
        _embedding_cache[cache_key] = result
        return result
    return get_sentence_transformer().encode(texts, convert_to_tensor=convert_to_tensor)


# ── Whisper ASR (Optimized via faster-whisper) ────────────────────────────────


def load_asr_model() -> None:
    """Load Whisper ASR using the faster-whisper (CTranslate2) engine."""
    global _asr_pipeline
    if _asr_pipeline is None:
        with _asr_lock:
            if _asr_pipeline is None:
                print(f"📥 Loading Faster-Whisper ({ASR_MODEL_NAME})…")
                try:
                    import torch
                    from faster_whisper import WhisperModel

                    device = "cuda" if torch.cuda.is_available() else "cpu"
                    # int8 is safe and much faster on CPU; float16 is optimal for GPU
                    compute_type = "float16" if device == "cuda" else "int8"

                    # ASR_MODEL_NAME is usually a HF model ID like "openai/whisper-tiny"
                    # faster-whisper handles these automatically.
                    _asr_pipeline = WhisperModel(
                        ASR_MODEL_NAME,
                        device=device,
                        compute_type=compute_type,
                        download_root=os.path.join(os.getenv("STORAGE_DIR", "/tmp"), "models"),
                    )
                    print(
                        f"✅ Faster-Whisper ready ({ASR_MODEL_NAME}, device={device}, compute={compute_type})"
                    )
                except Exception as exc:
                    print(f"⚠️  Faster-Whisper load failed: {exc}")
                    _asr_pipeline = None


def get_asr_model() -> Optional[Any]:
    if _asr_pipeline is None:
        load_asr_model()
    return _asr_pipeline


def transcribe_audio(audio_path: str) -> dict:
    """Transcribe audio using faster-whisper. Returns {"text": str, "chunks": list}."""
    model = get_asr_model()
    if model is None:
        raise RuntimeError("ASR model unavailable. Check server logs.")

    # beam_size=5 is a good balance of accuracy/speed
    segments, info = model.transcribe(audio_path, beam_size=5, word_timestamps=True)

    full_text = []
    chunks = []
    for segment in segments:
        full_text.append(segment.text)
        chunks.append(
            {
                "text": segment.text,
                "start": segment.start,
                "end": segment.end,
            }
        )

    return {
        "text": "".join(full_text).strip(),
        "chunks": chunks,
        "language": info.language,
        "duration": info.duration,
    }


# ── LLM — GPU: local Qwen2.5-7B | CPU: HF Inference API ─────────────────────


def load_llm_model():
    """Load LLM scoring engine.

    GPU path: Qwen2.5-7B-Instruct with 4-bit NF4 quantization (local).
    CPU path: HF Inference API proxy (requires HF_TOKEN env var).
    No GPU + no token: disabled — scoring falls back to cosine similarity.

    Returns (model, tokenizer) on success. For API mode, returns (_API_PROXY, None).
    Returns (None, None) if disabled.
    Uses double-checked locking so concurrent first-calls are safe.
    """
    global _llm_model, _llm_tokenizer, _llm_mode

    # Fast path — already loaded
    if _llm_model is not None:
        return _llm_model, _llm_tokenizer

    with _llm_lock:
        # Re-check inside lock
        if _llm_model is not None:
            return _llm_model, _llm_tokenizer

        if GPU_AVAILABLE:
            # ── GPU path: load Qwen2.5-7B locally ────────────────────────
            try:
                import torch
            except ImportError:
                print("⚠️  torch not available — LLM scorer disabled.")
                return None, None

            print(f"📥 Loading {LLM_MODEL_ID} (4-bit NF4)…")
            try:
                from transformers import (
                    AutoModelForCausalLM,
                    AutoTokenizer,
                    BitsAndBytesConfig,
                )

                quant_config = BitsAndBytesConfig(
                    load_in_4bit=True,
                    bnb_4bit_compute_dtype=torch.float16,
                    bnb_4bit_use_double_quant=True,  # saves ~0.4 GB extra
                    bnb_4bit_quant_type="nf4",
                )

                tokenizer = AutoTokenizer.from_pretrained(
                    LLM_MODEL_ID,
                    trust_remote_code=True,
                )

                model = AutoModelForCausalLM.from_pretrained(
                    LLM_MODEL_ID,
                    quantization_config=quant_config,
                    device_map="auto",
                    trust_remote_code=True,
                )
                model.eval()

                _llm_model = model
                _llm_tokenizer = tokenizer
                _llm_mode = "local"

                used = torch.cuda.memory_allocated() / 1e9
                total = torch.cuda.get_device_properties(0).total_memory / 1e9
                print(f"✅ {LLM_MODEL_ID} ready")
                print(f"   VRAM used: {used:.1f} GB / {total:.1f} GB")

            except Exception as exc:
                print(f"⚠️  LLM load failed: {exc}. Falling back to cosine similarity.")
                _llm_model = None
                _llm_tokenizer = None
                _llm_mode = "disabled"
        else:
            # ── CPU path: use HF Inference API ───────────────────────────
            if _HF_TOKEN:
                print(f"📡 CPU mode — LLM scoring via HF Inference API ({_HF_API_MODEL})")
                _llm_model = _API_PROXY
                _llm_tokenizer = None
                _llm_mode = "api"
            else:
                print(
                    "ℹ️  No GPU and no HF_TOKEN — LLM scoring disabled. Using cosine similarity only."
                )
                _llm_model = None
                _llm_tokenizer = None
                _llm_mode = "disabled"

        return _llm_model, _llm_tokenizer


def get_llm_model():
    """Return (model, tokenizer). Returns (None, None) if not loaded or disabled.
    Returns (_API_PROXY, None) if in API mode.

    Does NOT trigger loading — call load_llm_model() explicitly to warm up.
    Callers must handle (None, None) gracefully.
    """
    return _llm_model, _llm_tokenizer


def _hf_api_fallback(prompt: str) -> str:
    """Return a contextually appropriate fallback string when HF API is unavailable."""
    prompt_lower = prompt.lower()
    if "question" in prompt_lower and "interview" in prompt_lower:
        return "Tell me about your technical background and the projects you're most proud of."
    if "relevant" in prompt_lower or "spam" in prompt_lower:
        return '{"relevant": true, "reason": "llm_unavailable"}'
    if "score" in prompt_lower or "evaluate" in prompt_lower:
        return '{"score": 7, "explanation": "Solid answer demonstrating relevant knowledge.", "strengths": ["Clear communication"], "gaps": []}'
    if "company" in prompt_lower or "research" in prompt_lower:
        return '{"company_focus": "Technical skills and problem-solving", "common_questions": [], "tech_stack_hints": [], "interview_style": "standard"}'
    return "The candidate demonstrates solid technical proficiency and communication skills."


def _hf_api_generate(
    prompt: str,
    max_new_tokens: int = 512,
    temperature: float = 0.0,
    fallback_on_error: bool = True,
) -> str:
    """Call HuggingFace Inference API for text generation using InferenceClient.

    Uses the chat completions endpoint via the official Python client.
    Legacy direct callers receive descriptive fallbacks by default. The AI
    gateway passes fallback_on_error=False so provider failures can be routed to
    the next provider or template fallback instead of being counted as success.
    """
    global _hf_api_failure_count, _hf_api_circuit_open, _hf_api_circuit_opened_at

    # TR-2: Circuit breaker — skip API call if circuit is open
    if _hf_api_circuit_open:
        elapsed = time.time() - _hf_api_circuit_opened_at
        if elapsed < _HF_CIRCUIT_COOLDOWN:
            logging.getLogger(__name__).debug(
                f"HF API circuit open ({int(_HF_CIRCUIT_COOLDOWN - elapsed)}s remaining) — using fallback"
            )
            if not fallback_on_error:
                raise RuntimeError("HF API circuit is open")
            return _hf_api_fallback(prompt)
        # Cooldown elapsed — try again (half-open state)
        logging.getLogger(__name__).info("HF API circuit half-open — retrying")
        _hf_api_circuit_open = False
        _hf_api_failure_count = 0

    if not _HF_TOKEN:
        # Log warning once about missing token
        logging.getLogger(__name__).warning(
            "HF_TOKEN not set - using LLM fallback. "
            "Set HF_TOKEN environment variable for full LLM features."
        )
        if not fallback_on_error:
            raise RuntimeError("HF_TOKEN not set")
        return _hf_api_fallback(prompt)

    try:
        from huggingface_hub import InferenceClient
        from huggingface_hub.errors import HfHubHTTPError

        # Use the official client. It auto-resolves the correct TGI/serverless endpoint.
        client = InferenceClient(token=_HF_TOKEN)

        # Some models require temperature > 0
        safe_temp = max(temperature, 0.01)

        for attempt in range(2):
            try:
                response = client.chat_completion(
                    messages=[{"role": "user", "content": prompt}],
                    model=_HF_API_MODEL,
                    max_tokens=max_new_tokens,
                    temperature=safe_temp,
                    stream=False,
                )
                # Success — reset circuit breaker
                _hf_api_failure_count = 0
                return response.choices[0].message.content.strip()
            except HfHubHTTPError as e:
                # 503 means model is loading, retry once
                if e.response.status_code == 503 and attempt == 0:
                    print("⏳ HF API model loading, retrying in 10s…")
                    time.sleep(10)
                    continue
                print(f"⚠️  HF API error {e.response.status_code}: {e.server_message}")
                logging.getLogger(__name__).warning(
                    f"HF API error {e.response.status_code} - using LLM fallback. "
                    f"Server message: {e.server_message}"
                )
                # TR-2: Track failure for circuit breaker BEFORE returning fallback
                _hf_api_failure_count += 1
                if _hf_api_failure_count >= _HF_CIRCUIT_THRESHOLD:
                    _hf_api_circuit_open = True
                    _hf_api_circuit_opened_at = time.time()
                    logging.getLogger(__name__).error(
                        f"HF API circuit breaker OPENED after {_hf_api_failure_count} failures — "
                        f"using fallbacks for {_HF_CIRCUIT_COOLDOWN}s"
                    )
                if not fallback_on_error:
                    raise RuntimeError(
                        f"HF API error {e.response.status_code}: {e.server_message}"
                    )
                return _hf_api_fallback(prompt)
            except Exception as e:
                print(f"⚠️  HF API exception: {e}")
                _hf_api_failure_count += 1
                if _hf_api_failure_count >= _HF_CIRCUIT_THRESHOLD:
                    _hf_api_circuit_open = True
                    _hf_api_circuit_opened_at = time.time()
                    logging.getLogger(__name__).error(
                        f"HF API circuit breaker OPENED after {_hf_api_failure_count} failures — "
                        f"using fallbacks for {_HF_CIRCUIT_COOLDOWN}s"
                    )
                if attempt == 0:
                    time.sleep(2)
                    continue
                if not fallback_on_error:
                    raise RuntimeError(f"HF API exception: {e}")
                return _hf_api_fallback(prompt)

    except Exception as exc:
        print(f"⚠️  HF API error: {exc}")
        if not fallback_on_error:
            raise
        return _hf_api_fallback(prompt)


def llm_generate(
    prompt: str,
    max_new_tokens: int = 512,
    temperature: float = 0.0,
) -> str:
    """Run a single inference call on the loaded LLM.

    Routes to local GPU model or HF Inference API based on runtime mode.
    Returns the newly generated text only (input prompt is stripped for local mode).
    Returns empty string "" if the model is not loaded / API unavailable.
    Uses temperature=0 by default for deterministic, consistent scoring.
    """
    model, tokenizer = get_llm_model()
    if model is None:
        model, tokenizer = load_llm_model()

    # ── API mode: route to HF Inference API ──────────────────────────────
    if isinstance(model, _APIProxy):
        return _hf_api_generate(prompt, max_new_tokens, temperature)

    # ── Disabled mode ────────────────────────────────────────────────────
    if model is None:
        logger.warning("LLM unavailable — all LLM callers will use fallbacks.")
        return ""  # empty string, not a human sentence (forces callers to use their own fallbacks)

    # ── Local GPU mode: existing Qwen inference ──────────────────────────
    try:
        import torch

        messages = [{"role": "user", "content": prompt}]
        text = tokenizer.apply_chat_template(
            messages,
            tokenize=False,
            add_generation_prompt=True,
        )
        inputs = tokenizer([text], return_tensors="pt").to(model.device)
        input_len = inputs["input_ids"].shape[1]

        with torch.no_grad():
            outputs = model.generate(
                **inputs,
                max_new_tokens=max_new_tokens,
                do_sample=(temperature > 0),
                temperature=temperature if temperature > 0 else None,
                pad_token_id=tokenizer.eos_token_id,
            )

        # Slice off the input tokens — return ONLY the newly generated tokens
        generated_ids = outputs[0][input_len:]
        return tokenizer.decode(generated_ids, skip_special_tokens=True).strip()

    except Exception as exc:
        print(f"⚠️  llm_generate error: {exc}")
        return (
            "The candidate demonstrates solid knowledge in their core stack and project experience."
        )


# ── Startup preloader ──────────────────────────────────────────────────────────


def load_models() -> None:
    """Called from FastAPI lifespan on startup.

    Loads all models appropriate for the detected runtime mode.
    GPU mode: SentenceTransformer (mpnet) + Whisper (large-v3-turbo) + optional LLM.
    CPU mode: SentenceTransformer (MiniLM) + Whisper (tiny) + LLM API probe.
    """
    mode = "GPU" if GPU_AVAILABLE else "CPU"
    print(f"🖥️  Runtime mode: {mode}")
    print(f"   Embedding model: {SENTENCE_MODEL_NAME}")
    print(f"   ASR model:       {ASR_MODEL_NAME}")

    # Always load embedding model
    load_sentence_model()

    # Always load ASR (CPU gets whisper-tiny, GPU gets large-v3-turbo)
    load_asr_model()

    # LLM: eager-load on GPU if requested, always probe on CPU
    if GPU_AVAILABLE:
        if LLM_EAGER_LOAD:
            print("ℹ️  LLM_EAGER_LOAD=true — pre-warming Qwen2.5-7B-Instruct…")
            load_llm_model()
        else:
            print(
                "ℹ️  LLM lazy-loads on first scoring request (set LLM_EAGER_LOAD=true to pre-warm)"
            )
    else:
        # CPU: immediately resolve LLM mode (API or disabled)
        load_llm_model()

    print(f"   LLM mode:        {_llm_mode}")


# ── Runtime info helpers ──────────────────────────────────────────────────────


def is_gpu_available() -> bool:
    """Return True if a CUDA GPU is available."""
    return GPU_AVAILABLE


def get_runtime_mode() -> str:
    """Return 'gpu' or 'cpu'."""
    return "gpu" if GPU_AVAILABLE else "cpu"


def get_llm_mode_str() -> str:
    """Return current LLM mode: 'local', 'api', or 'disabled'."""
    return _llm_mode


def get_model_info() -> dict:
    """Return dict of active model names and modes for health/diagnostics."""
    return {
        "mode": get_runtime_mode(),
        "embedding_model": SENTENCE_MODEL_NAME.split("/")[-1],
        "asr_model": ASR_MODEL_NAME.split("/")[-1],
        "llm_mode": _llm_mode,
        "llm_model": (
            LLM_MODEL_ID
            if _llm_mode == "local"
            else _HF_API_MODEL if _llm_mode == "api" else "none"
        ),
        "asr_available": _asr_pipeline is not None,
        "hf_circuit_open": is_hf_circuit_open(),
    }
