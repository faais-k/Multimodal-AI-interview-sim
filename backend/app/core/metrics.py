"""
Observability & Metrics Module — Prometheus instrumentation for the AI Interview Simulator.

Exposes counters and histograms for:
  - HTTP requests (by route, method, status code)
  - LLM inference calls (by provider, task, outcome)
  - Interview lifecycle events (sessions started, completed, reported)
  - ASR transcription (count, latency)
  - Score distribution

Usage:
    from backend.app.core.metrics import (
        record_request, record_llm_call, record_interview_event,
        record_asr_transcription, inc_active_sessions, dec_active_sessions,
    )

Prometheus endpoint is served at /metrics by the metrics router.
"""

import os
import time
import logging
from typing import Optional

logger = logging.getLogger(__name__)

# ── Check if prometheus_client is available ───────────────────────────────────
_PROMETHEUS_ENABLED = False
try:
    from prometheus_client import (
        Counter,
        Histogram,
        Gauge,
        CollectorRegistry,
        generate_latest,
        CONTENT_TYPE_LATEST,
        REGISTRY,
    )

    _PROMETHEUS_ENABLED = True
except ImportError:
    logger.warning(
        "prometheus_client not installed — metrics endpoint will return stub data. "
        "Install with: pip install prometheus-client"
    )


# ── Metric definitions (only created if prometheus available) ─────────────────

if _PROMETHEUS_ENABLED:
    # HTTP request metrics
    HTTP_REQUESTS_TOTAL = Counter(
        "ascent_http_requests_total",
        "Total HTTP requests processed",
        ["method", "endpoint", "status_code"],
    )
    HTTP_REQUEST_DURATION = Histogram(
        "ascent_http_request_duration_seconds",
        "HTTP request latency in seconds",
        ["method", "endpoint"],
        buckets=[0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0],
    )

    # LLM inference metrics
    LLM_CALLS_TOTAL = Counter(
        "ascent_llm_calls_total",
        "Total LLM inference calls",
        ["provider", "task", "outcome"],  # outcome: success | fallback | error
    )
    LLM_LATENCY = Histogram(
        "ascent_llm_latency_seconds",
        "LLM inference latency in seconds",
        ["provider", "task"],
        buckets=[0.5, 1.0, 2.5, 5.0, 10.0, 20.0, 30.0, 60.0],
    )

    # Interview lifecycle metrics
    SESSIONS_STARTED = Counter(
        "ascent_sessions_started_total",
        "Total interview sessions started",
    )
    SESSIONS_COMPLETED = Counter(
        "ascent_sessions_completed_total",
        "Total interview sessions completed",
    )
    REPORTS_GENERATED = Counter(
        "ascent_reports_generated_total",
        "Total final reports generated",
    )
    ACTIVE_SESSIONS = Gauge(
        "ascent_active_sessions",
        "Number of currently active interview sessions",
    )

    # ASR metrics
    ASR_TRANSCRIPTIONS_TOTAL = Counter(
        "ascent_asr_transcriptions_total",
        "Total audio transcription calls",
        ["outcome"],  # success | error | timeout
    )
    ASR_LATENCY = Histogram(
        "ascent_asr_latency_seconds",
        "Whisper ASR latency in seconds",
        buckets=[1.0, 2.5, 5.0, 10.0, 20.0, 45.0, 90.0],
    )

    # Score distribution
    ANSWER_SCORES = Histogram(
        "ascent_answer_scores",
        "Distribution of answer scores (0-10)",
        ["scorer"],  # llm | cosine
        buckets=[1, 2, 3, 4, 5, 6, 7, 8, 9, 10],
    )

    # Circuit breaker state
    HF_CIRCUIT_OPEN = Gauge(
        "ascent_hf_circuit_open",
        "1 if HuggingFace API circuit breaker is open, 0 otherwise",
    )


# ── Public recording functions ────────────────────────────────────────────────


def record_request(method: str, endpoint: str, status_code: int, duration_s: float) -> None:
    """Record an HTTP request completion."""
    if not _PROMETHEUS_ENABLED:
        return
    try:
        # Normalise endpoint — strip session IDs and UUIDs for cardinality safety
        HTTP_REQUESTS_TOTAL.labels(
            method=method,
            endpoint=_normalise_endpoint(endpoint),
            status_code=str(status_code),
        ).inc()
        HTTP_REQUEST_DURATION.labels(
            method=method,
            endpoint=_normalise_endpoint(endpoint),
        ).observe(duration_s)
    except Exception as exc:
        logger.debug(f"[metrics] record_request error: {exc}")


def record_llm_call(
    provider: str,
    task: str,
    outcome: str,  # "success" | "fallback" | "error"
    latency_s: float,
) -> None:
    """Record a single LLM inference call outcome."""
    if not _PROMETHEUS_ENABLED:
        return
    try:
        LLM_CALLS_TOTAL.labels(provider=provider, task=task, outcome=outcome).inc()
        LLM_LATENCY.labels(provider=provider, task=task).observe(latency_s)
        # Update circuit breaker gauge
        from backend.app.core.ml_models import is_hf_circuit_open

        HF_CIRCUIT_OPEN.set(1.0 if is_hf_circuit_open() else 0.0)
    except Exception as exc:
        logger.debug(f"[metrics] record_llm_call error: {exc}")


def record_interview_event(event: str) -> None:
    """Record interview lifecycle event: 'started' | 'completed' | 'reported'."""
    if not _PROMETHEUS_ENABLED:
        return
    try:
        if event == "started":
            SESSIONS_STARTED.inc()
            ACTIVE_SESSIONS.inc()
        elif event == "completed":
            SESSIONS_COMPLETED.inc()
            ACTIVE_SESSIONS.dec()
        elif event == "reported":
            REPORTS_GENERATED.inc()
    except Exception as exc:
        logger.debug(f"[metrics] record_interview_event error: {exc}")


def record_asr_transcription(outcome: str, latency_s: float) -> None:
    """Record an ASR transcription attempt."""
    if not _PROMETHEUS_ENABLED:
        return
    try:
        ASR_TRANSCRIPTIONS_TOTAL.labels(outcome=outcome).inc()
        if outcome == "success":
            ASR_LATENCY.observe(latency_s)
    except Exception as exc:
        logger.debug(f"[metrics] record_asr_transcription error: {exc}")


def record_answer_score(score: float, scorer: str) -> None:
    """Record an individual answer score for distribution tracking."""
    if not _PROMETHEUS_ENABLED:
        return
    try:
        ANSWER_SCORES.labels(scorer=scorer).observe(score)
    except Exception as exc:
        logger.debug(f"[metrics] record_answer_score error: {exc}")


def get_metrics_output() -> tuple[bytes, str]:
    """
    Return (metrics_bytes, content_type) for the /metrics endpoint.
    Returns stub data if prometheus_client is not installed.
    """
    if _PROMETHEUS_ENABLED:
        return generate_latest(REGISTRY), CONTENT_TYPE_LATEST
    # Stub response so the endpoint exists even without prometheus_client
    stub = b"# prometheus_client not installed\n# Install with: pip install prometheus-client\n"
    return stub, "text/plain; version=0.0.4; charset=utf-8"


def is_metrics_enabled() -> bool:
    """Return True if Prometheus metrics are available."""
    return _PROMETHEUS_ENABLED


# ── Internal helpers ──────────────────────────────────────────────────────────

_UUID_PATTERN = None


def _normalise_endpoint(path: str) -> str:
    """
    Replace UUID segments and numeric IDs with placeholders to keep
    Prometheus label cardinality bounded.

    /api/session/abc-def-123 → /api/session/{session_id}
    /api/report/abc-def-123  → /api/report/{session_id}
    """
    global _UUID_PATTERN
    if _UUID_PATTERN is None:
        import re

        _UUID_PATTERN = re.compile(
            r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}",
            re.IGNORECASE,
        )
    return _UUID_PATTERN.sub("{session_id}", path)
