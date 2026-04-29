"""
AI Orchestration Gateway — Multi-Provider LLM Abstraction Layer.

Provides a single unified interface for all LLM calls in the system.
Handles provider routing, retries with exponential backoff, circuit
breaking, timeouts, and structured observability logging.

Provider Priority Order (configured via env vars):
  1. Primary:   HuggingFace Inference API (serverless, cloud)
  2. Secondary: Local GPU model (Qwen2.5-7B if CUDA available)
  3. Tertiary:  Static template fallbacks (always works, no AI)

Usage:
    from backend.app.core.ai_gateway import ai_generate

    result = await ai_generate(
        prompt="...",
        task="question_generation",   # for logging
        max_tokens=300,
        temperature=0.7,
    )
    print(result.text)         # the generated string
    print(result.provider)     # which provider was used
    print(result.used_fallback) # True if fell back to templates
"""

import asyncio
import logging
import os
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)

# ── Configuration ────────────────────────────────────────────────────────────

# Max time (seconds) for a single LLM provider attempt before timeout
_LLM_TIMEOUT = float(os.getenv("LLM_TIMEOUT_SECONDS", "30"))

# Retry configuration per provider
_MAX_RETRIES = int(os.getenv("LLM_MAX_RETRIES", "2"))
_RETRY_BASE_DELAY = float(os.getenv("LLM_RETRY_BASE_DELAY", "1.5"))  # seconds


# ── Result dataclass ─────────────────────────────────────────────────────────

@dataclass
class AIResult:
    """Structured result from an AI gateway call."""
    text: str
    provider: str               # "hf_api" | "local_gpu" | "template_fallback"
    task: str                   # task label passed in by caller
    request_id: str             # unique ID for tracing this call
    latency_ms: float           # total time spent (ms)
    retries: int = 0            # number of retries before success
    used_fallback: bool = False # True if no AI provider succeeded
    error: Optional[str] = None # last error message if any fallback was used


# ── Internal provider callables ──────────────────────────────────────────────

def _call_hf_api(prompt: str, max_tokens: int, temperature: float) -> str:
    """Call the HuggingFace Inference API synchronously."""
    from backend.app.core.ml_models import _hf_api_generate, is_hf_circuit_open
    if is_hf_circuit_open():
        raise RuntimeError("HF API circuit is open — skipping")
    result = _hf_api_generate(prompt, max_new_tokens=max_tokens, temperature=temperature)
    if not result or len(result.strip()) < 5:
        raise ValueError("HF API returned empty or trivial response")
    return result.strip()


def _call_local_gpu(prompt: str, max_tokens: int, temperature: float) -> str:
    """Call the local GPU model synchronously."""
    from backend.app.core.ml_models import llm_generate, is_gpu_available, get_llm_mode_str
    if not is_gpu_available():
        raise RuntimeError("No GPU available for local model")
    if get_llm_mode_str() != "local":
        raise RuntimeError("Local GPU model not loaded")
    result = llm_generate(prompt, max_new_tokens=max_tokens, temperature=temperature)
    if not result or len(result.strip()) < 5:
        raise ValueError("Local model returned empty or trivial response")
    return result.strip()


# ── Provider registry ────────────────────────────────────────────────────────

# List of (provider_name, callable) in priority order.
# Each callable accepts (prompt, max_tokens, temperature) → str
_PROVIDERS: list[tuple[str, Callable]] = [
    ("hf_api",    _call_hf_api),
    ("local_gpu", _call_local_gpu),
]


# ── Retry helper ─────────────────────────────────────────────────────────────

async def _try_provider_with_retry(
    provider_name: str,
    fn: Callable,
    prompt: str,
    max_tokens: int,
    temperature: float,
    request_id: str,
    task: str,
) -> tuple[str, int]:
    """
    Attempt a provider with exponential backoff retries.

    Returns (text, retries_used) on success.
    Raises the last exception on failure after all retries.
    """
    last_exc: Exception = RuntimeError("Unknown error")
    for attempt in range(_MAX_RETRIES + 1):
        try:
            start = time.monotonic()
            # Run synchronous provider in thread pool with timeout
            text = await asyncio.wait_for(
                asyncio.to_thread(fn, prompt, max_tokens, temperature),
                timeout=_LLM_TIMEOUT,
            )
            latency = (time.monotonic() - start) * 1000
            logger.info(
                f"[AI-GW] req={request_id} task={task} provider={provider_name} "
                f"attempt={attempt+1} latency={latency:.0f}ms ✓"
            )
            return text, attempt
        except asyncio.TimeoutError:
            last_exc = TimeoutError(f"Provider '{provider_name}' timed out after {_LLM_TIMEOUT}s")
            logger.warning(
                f"[AI-GW] req={request_id} task={task} provider={provider_name} "
                f"attempt={attempt+1} TIMEOUT"
            )
        except Exception as exc:
            last_exc = exc
            logger.warning(
                f"[AI-GW] req={request_id} task={task} provider={provider_name} "
                f"attempt={attempt+1} FAILED: {exc}"
            )
        # Exponential backoff before next retry
        if attempt < _MAX_RETRIES:
            delay = _RETRY_BASE_DELAY * (2 ** attempt)
            logger.debug(f"[AI-GW] Retrying in {delay:.1f}s…")
            await asyncio.sleep(delay)

    raise last_exc


# ── Public gateway function ──────────────────────────────────────────────────

async def ai_generate(
    prompt: str,
    task: str = "general",
    max_tokens: int = 512,
    temperature: float = 0.3,
    fallback_text: Optional[str] = None,
) -> AIResult:
    """
    Generate text using the best available AI provider.

    Tries providers in priority order (HF API → Local GPU).
    On all failures, returns `fallback_text` or a safe default.
    Logs every attempt, route switch, and fallback for observability.

    Args:
        prompt:        The instruction/prompt for the LLM.
        task:          Label for logging/tracing (e.g. "question_generation").
        max_tokens:    Maximum output tokens.
        temperature:   Sampling temperature (0 = deterministic).
        fallback_text: Text to return if ALL providers fail. If None,
                       a generic safe message is used.

    Returns:
        AIResult with .text, .provider, .used_fallback, .latency_ms, etc.
    """
    request_id = str(uuid.uuid4())[:8]
    overall_start = time.monotonic()
    last_error: Optional[str] = None
    total_retries = 0

    logger.info(
        f"[AI-GW] START req={request_id} task={task} "
        f"max_tokens={max_tokens} temp={temperature}"
    )

    for provider_name, provider_fn in _PROVIDERS:
        try:
            text, retries = await _try_provider_with_retry(
                provider_name, provider_fn,
                prompt, max_tokens, temperature,
                request_id, task,
            )
            total_retries += retries
            latency_ms = (time.monotonic() - overall_start) * 1000
            logger.info(
                f"[AI-GW] DONE req={request_id} task={task} "
                f"provider={provider_name} total_retries={total_retries} "
                f"total_latency={latency_ms:.0f}ms"
            )
            return AIResult(
                text=text,
                provider=provider_name,
                task=task,
                request_id=request_id,
                latency_ms=latency_ms,
                retries=total_retries,
                used_fallback=False,
            )
        except Exception as exc:
            last_error = str(exc)
            logger.error(
                f"[AI-GW] PROVIDER_FAILED req={request_id} task={task} "
                f"provider={provider_name} — switching to next provider. Error: {exc}"
            )

    # All providers exhausted — use template fallback
    latency_ms = (time.monotonic() - overall_start) * 1000
    safe_fallback = fallback_text or (
        "Tell me about a recent project you worked on and the technical challenges you faced."
    )
    logger.error(
        f"[AI-GW] ALL_PROVIDERS_FAILED req={request_id} task={task} "
        f"total_latency={latency_ms:.0f}ms — using template fallback. last_error={last_error}"
    )
    return AIResult(
        text=safe_fallback,
        provider="template_fallback",
        task=task,
        request_id=request_id,
        latency_ms=latency_ms,
        retries=total_retries,
        used_fallback=True,
        error=last_error,
    )


# ── Convenience wrappers ─────────────────────────────────────────────────────

async def generate_interview_question(
    prompt: str,
    fallback: str = "Tell me about your most impactful project and the decisions you made.",
) -> AIResult:
    """Wrapper for interview question generation tasks."""
    return await ai_generate(
        prompt=prompt,
        task="question_generation",
        max_tokens=250,
        temperature=0.7,
        fallback_text=fallback,
    )


async def score_answer_llm(
    prompt: str,
    fallback: str = '{"raw_score": 6.0, "explanation": "Solid answer.", "strengths": [], "gaps": []}',
) -> AIResult:
    """Wrapper for LLM-based answer scoring tasks."""
    return await ai_generate(
        prompt=prompt,
        task="answer_scoring",
        max_tokens=512,
        temperature=0.0,  # Deterministic for scoring
        fallback_text=fallback,
    )


async def generate_followup_question(
    prompt: str,
    fallback: str = "Could you elaborate on that point with a specific example?",
) -> AIResult:
    """Wrapper for dynamic follow-up question generation."""
    return await ai_generate(
        prompt=prompt,
        task="followup_generation",
        max_tokens=150,
        temperature=0.5,
        fallback_text=fallback,
    )
