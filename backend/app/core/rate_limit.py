"""
Simple in-memory per-session, per-endpoint rate limiter.

Uses a sliding window approach. Safe for single-process deployments.
Not shared across multiple uvicorn workers — acceptable for this use case.
"""

import asyncio
from collections import defaultdict
from datetime import datetime, timedelta

_request_counts: dict = defaultdict(list)
_rate_lock: asyncio.Lock | None = None

def _get_rate_lock() -> asyncio.Lock:
    global _rate_lock
    if _rate_lock is None:
        _rate_lock = asyncio.Lock()
    return _rate_lock


async def check_rate_limit(
    session_id: str,
    endpoint: str,
    max_requests: int = 30,
    window_seconds: int = 60,
) -> bool:
    """Return True if the request is allowed, False if rate limit exceeded.

    Tracks per (session_id, endpoint) pairs using a sliding time window.
    Expired timestamps are pruned on each check.
    """
    async with _get_rate_lock():
        key = f"{session_id}:{endpoint}"
        now = datetime.utcnow()
        window_start = now - timedelta(seconds=window_seconds)

        # Prune timestamps outside the current window
        _request_counts[key] = [
            ts for ts in _request_counts[key] if ts > window_start
        ]

        if len(_request_counts[key]) >= max_requests:
            return False  # rate limit exceeded

        _request_counts[key].append(now)

        # Memory guard: prevent unbounded growth over many sessions
        if len(_request_counts) > 10000:
            empty_keys = [k for k, v in _request_counts.items() if not v]
            for k in empty_keys:
                del _request_counts[k]

        return True
