"""
Prometheus metrics endpoint.

Exposes /api/metrics for scraping by Prometheus or Grafana Agent.
Requires the METRICS_TOKEN env var to protect the endpoint from public access.
If METRICS_TOKEN is unset, the endpoint is open (suitable for trusted networks).
"""

import os
from fastapi import APIRouter, HTTPException, Header
from fastapi.responses import Response

from backend.app.core.metrics import get_metrics_output, is_metrics_enabled

router = APIRouter(tags=["Observability"])

_METRICS_TOKEN = os.getenv("METRICS_TOKEN", "")


@router.get("/metrics")
async def prometheus_metrics(authorization: str = Header(default="")):
    """
    Prometheus scrape endpoint.

    Returns text/plain metrics in Prometheus exposition format.
    Optionally protected by a bearer token (set METRICS_TOKEN env var).
    """
    # Token-based auth guard (optional but recommended for production)
    if _METRICS_TOKEN:
        expected = f"Bearer {_METRICS_TOKEN}"
        if authorization != expected:
            raise HTTPException(
                status_code=401,
                detail="Unauthorized. Set 'Authorization: Bearer <METRICS_TOKEN>' header.",
            )

    body, content_type = get_metrics_output()
    return Response(content=body, media_type=content_type)


@router.get("/metrics/status")
async def metrics_status():
    """Returns whether Prometheus metrics collection is active."""
    return {
        "metrics_enabled": is_metrics_enabled(),
        "scrape_endpoint": "/api/metrics",
        "note": "Install prometheus-client to enable full metrics collection."
        if not is_metrics_enabled()
        else "Metrics active. Scrape /api/metrics for Prometheus exposition format.",
    }
