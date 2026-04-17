"""
Centralised ML model loading.

Models:
  Embeddings : sentence-transformers/all-mpnet-base-v2
  ASR        : openai/whisper-large-v3-turbo
  LLM        : Qwen/Qwen2.5-7B-Instruct (4-bit NF4 quant, lazy by default)

VRAM budget on Colab T4 (15 GB):
  Qwen2.5-7B 4-bit  ~4.5 GB
  Whisper large-v3-turbo  ~2.0 GB
  all-mpnet-base-v2  ~0.5 GB
  ─────────────────────────
  Total  ~7.0 GB  (fits with room to spare)

LLM loading behaviour:
  Default: lazy — loads on first call to llm_generate().
  Set env var LLM_EAGER_LOAD=true to pre-warm at startup (adds ~90s).
"""

import os
import threading
from typing import Any, List, Optional, Union

# ── LLM imports (checked at use-time so the file imports cleanly on CPU hosts) ─
_SENTENCE_MODEL_NAME = "sentence-transformers/all-mpnet-base-v2"
_ASR_MODEL_NAME      = "openai/whisper-large-v3-turbo"
LLM_MODEL_ID         = "Qwen/Qwen2.5-7B-Instruct"

# Controls whether LLM is pre-warmed at startup (set via env var)
LLM_EAGER_LOAD = os.getenv("LLM_EAGER_LOAD", "false").lower() == "true"

# ── Module-level singletons ───────────────────────────────────────────────────

_sentence_model:  Optional[Any] = None
_asr_pipeline:    Optional[Any] = None
_llm_model:       Optional[Any] = None
_llm_tokenizer:   Optional[Any] = None

_sentence_lock = threading.Lock()
_asr_lock      = threading.Lock()
_llm_lock      = threading.Lock()


# ── Sentence Transformer ───────────────────────────────────────────────────────

def load_sentence_model() -> None:
    global _sentence_model
    if _sentence_model is None:
        with _sentence_lock:
            if _sentence_model is None:
                print(f"📥 Loading SentenceTransformer ({_SENTENCE_MODEL_NAME})…")
                from sentence_transformers import SentenceTransformer
                _sentence_model = SentenceTransformer(_SENTENCE_MODEL_NAME)
                print("✅ SentenceTransformer ready")


def get_sentence_transformer() -> Any:
    if _sentence_model is None:
        load_sentence_model()
    return _sentence_model


def encode_sentence(texts: Union[str, List[str]], convert_to_tensor: bool = True) -> Any:
    return get_sentence_transformer().encode(texts, convert_to_tensor=convert_to_tensor)


# ── Whisper ASR ────────────────────────────────────────────────────────────────

def load_asr_model() -> None:
    global _asr_pipeline
    if _asr_pipeline is None:
        with _asr_lock:
            if _asr_pipeline is None:
                print(f"📥 Loading Whisper ASR ({_ASR_MODEL_NAME})…")
                try:
                    import torch
                    from transformers import pipeline as hf_pipeline
                    device = "cuda" if torch.cuda.is_available() else "cpu"
                    _asr_pipeline = hf_pipeline(
                        "automatic-speech-recognition",
                        model=_ASR_MODEL_NAME,
                        device=device,
                        chunk_length_s=30,
                        stride_length_s=5,
                        return_timestamps=True,
                    )
                    print(f"✅ Whisper ASR ready (device={device})")
                except Exception as exc:
                    print(f"⚠️  Whisper load failed: {exc}. ASR endpoints will be unavailable.")
                    _asr_pipeline = None


def get_asr_pipeline() -> Optional[Any]:
    if _asr_pipeline is None:
        load_asr_model()
    return _asr_pipeline


def transcribe_audio(audio_path: str) -> dict:
    """Transcribe audio. Returns {"text": str, "chunks": list}.
    Raises RuntimeError if ASR unavailable."""
    asr = get_asr_pipeline()
    if asr is None:
        raise RuntimeError("ASR model unavailable. Check server logs.")
    result = asr(audio_path)
    if isinstance(result, dict):
        text   = result.get("text", "").strip()
        chunks = result.get("chunks", [])
    else:
        text   = str(result).strip()
        chunks = []
    return {"text": text, "chunks": chunks}


# ── LLM — Qwen2.5-7B-Instruct (4-bit NF4) ────────────────────────────────────

def load_llm_model():
    """Load Qwen2.5-7B-Instruct with 4-bit NF4 quantization.

    Returns (model, tokenizer) on success, (None, None) if GPU unavailable.
    Uses double-checked locking so concurrent first-calls are safe.
    """
    global _llm_model, _llm_tokenizer

    # Fast path — already loaded
    if _llm_model is not None:
        return _llm_model, _llm_tokenizer

    with _llm_lock:
        # Re-check inside lock (another thread may have loaded while we waited)
        if _llm_model is not None:
            return _llm_model, _llm_tokenizer

        try:
            import torch
        except ImportError:
            print("⚠️  torch not available — LLM scorer disabled.")
            return None, None

        if not torch.cuda.is_available():
            print("⚠️  No GPU — LLM scorer unavailable. Falling back to cosine similarity.")
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
                bnb_4bit_use_double_quant=True,   # saves ~0.4 GB extra
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

            _llm_model     = model
            _llm_tokenizer = tokenizer

            used  = torch.cuda.memory_allocated() / 1e9
            total = torch.cuda.get_device_properties(0).total_memory / 1e9
            print(f"✅ {LLM_MODEL_ID} ready")
            print(f"   VRAM used: {used:.1f} GB / {total:.1f} GB")

        except Exception as exc:
            print(f"⚠️  LLM load failed: {exc}. Falling back to cosine similarity.")
            _llm_model     = None
            _llm_tokenizer = None

        return _llm_model, _llm_tokenizer


def get_llm_model():
    """Return (model, tokenizer). Returns (None, None) if not loaded or GPU absent.

    Does NOT trigger loading — call load_llm_model() explicitly to warm up.
    Callers must handle (None, None) gracefully.
    """
    return _llm_model, _llm_tokenizer


def llm_generate(
    prompt: str,
    max_new_tokens: int = 512,
    temperature: float = 0.0,
) -> str:
    """Run a single inference call on the loaded LLM.

    Returns the newly generated text only (input prompt is stripped).
    Returns empty string "" if the model is not loaded (GPU absent / not warmed).
    Uses temperature=0 by default for deterministic, consistent scoring.
    """
    model, tokenizer = get_llm_model()
    if model is None or tokenizer is None:
        return ""

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
        return ""


# ── Startup preloader ──────────────────────────────────────────────────────────

def load_models() -> None:
    """Called from FastAPI lifespan on startup.

    Always pre-loads: SentenceTransformer + Whisper (if GPU).
    LLM: only pre-loaded if LLM_EAGER_LOAD=true env var is set.
    """
    load_sentence_model()

    try:
        import torch
        if torch.cuda.is_available():
            load_asr_model()
        else:
            print("ℹ️  No GPU — Whisper lazy-loads on first audio request.")
    except ImportError:
        pass

    if LLM_EAGER_LOAD:
        print("ℹ️  LLM_EAGER_LOAD=true — pre-warming Qwen2.5-7B-Instruct…")
        load_llm_model()
    else:
        print("ℹ️  LLM lazy-loads on first scoring request (set LLM_EAGER_LOAD=true to pre-warm)")


# ── GPU availability check ─────────────────────────────────────────────────────

def is_gpu_available() -> bool:
    """Return True if a CUDA GPU is available."""
    try:
        import torch
        return torch.cuda.is_available()
    except ImportError:
        return False
