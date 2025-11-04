"""
Observability client to send logs and metrics to the Monitoring&Logging service.

Uses environment variables via Settings:
- OBS_ENABLED (bool): enable/disable sending
- OBS_ENDPOINT (str): base URL of the observability service (e.g., http://monitoring:8000)
- OBS_API_KEY (str): bearer token for authentication
- OBS_SERVICE_NAME, OBS_ENVIRONMENT: metadata

Endpoints used (Monitoring&Logging API spec):
- POST {OBS_ENDPOINT}/logs/ingest
- POST {OBS_ENDPOINT}/metrics/ingest
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Optional

import httpx

from src.core.config import get_settings
from src.core.logging import get_logger, get_correlation_id

logger = get_logger("observability")


def _auth_headers() -> Dict[str, str]:
    settings = get_settings()
    headers: Dict[str, str] = {"Content-Type": "application/json"}
    if settings.OBS_API_KEY:
        headers["Authorization"] = f"Bearer {settings.OBS_API_KEY}"
    return headers


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# PUBLIC_INTERFACE
async def send_log(level: str, message: str, metadata: Optional[Dict[str, Any]] = None) -> None:
    """Send a log entry to Monitoring&Logging, best-effort (errors swallowed)."""
    settings = get_settings()
    if not settings.OBS_ENABLED or not settings.OBS_ENDPOINT:
        return

    payload: Dict[str, Any] = {
        "source": settings.OBS_SERVICE_NAME,
        "timestamp": _now_iso(),
        "level": level.upper(),
        "message": message,
        "metadata": {
            "environment": settings.OBS_ENVIRONMENT,
        },
    }
    if metadata:
        payload["metadata"].update(metadata)
    cid = get_correlation_id()
    if cid:
        payload["metadata"]["correlation_id"] = cid

    url = settings.OBS_ENDPOINT.rstrip("/") + "/logs/ingest"

    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            await client.post(url, headers=_auth_headers(), json=payload)
    except Exception as exc:
        # Do not raise; just log locally
        logger.debug("Failed to send log to observability service", extra={"error": str(exc)})


# PUBLIC_INTERFACE
async def send_metric(name: str, metrics: Dict[str, Any], metadata: Optional[Dict[str, Any]] = None) -> None:
    """Send a metrics payload to Monitoring&Logging, best-effort (errors swallowed)."""
    settings = get_settings()
    if not settings.OBS_ENABLED or not settings.OBS_ENDPOINT:
        return

    payload: Dict[str, Any] = {
        "source": settings.OBS_SERVICE_NAME,
        "timestamp": _now_iso(),
        "metrics": {
            "name": name,
            **metrics,
        },
    }
    if metadata:
        payload.setdefault("metadata", {}).update(metadata)
    cid = get_correlation_id()
    if cid:
        payload.setdefault("metadata", {})["correlation_id"] = cid

    url = settings.OBS_ENDPOINT.rstrip("/") + "/metrics/ingest"

    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            await client.post(url, headers=_auth_headers(), json=payload)
    except Exception as exc:
        logger.debug("Failed to send metric to observability service", extra={"error": str(exc)})
