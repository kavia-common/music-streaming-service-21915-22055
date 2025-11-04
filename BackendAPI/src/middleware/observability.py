"""
Observability middleware for FastAPI/Starlette.

Features:
- Assign and propagate correlation IDs per request (from X-Request-ID or generated)
- Measure request latency and record status code
- Emit structured logs on request start and end
- Forward metrics/logs to Monitoring&Logging via services.observability

Headers:
- Reads X-Request-ID as incoming correlation id if provided
- Sets X-Correlation-ID on the response

Enabled via Settings.OBS_ENABLED; mounted conditionally in app.
"""

from __future__ import annotations

import time
from typing import Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from src.core.logging import get_logger, set_correlation_id, clear_correlation_id, get_correlation_id
from src.services.observability import send_log, send_metric

logger = get_logger("observability.middleware")


class ObservabilityMiddleware(BaseHTTPMiddleware):
    """Middleware to log and measure requests."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Correlation ID setup
        incoming_cid = request.headers.get("X-Request-ID") or request.headers.get("X-Correlation-ID")
        cid = set_correlation_id(incoming_cid)

        path = request.url.path
        method = request.method

        # Request started
        try:
            await send_log("INFO", "request.start", metadata={"method": method, "path": path})
        except Exception:
            pass  # swallow any issues

        start = time.perf_counter()
        status_code = 500
        try:
            response = await call_next(request)
            status_code = response.status_code
        except Exception as exc:
            # Emit an error log upstream and re-raise
            try:
                await send_log("ERROR", "request.exception", metadata={"method": method, "path": path, "error": str(exc)})
            except Exception:
                pass
            logger.exception("Unhandled exception in request", extra={"path": path, "method": method})
            raise
        finally:
            duration_ms = (time.perf_counter() - start) * 1000.0
            # Add correlation id header
            current_cid = get_correlation_id() or cid
            try:
                # Fire-and-forget metrics
                await send_metric(
                    name="http_request",
                    metrics={"duration_ms": duration_ms, "status_code": status_code, "count": 1},
                    metadata={"method": method, "path": path},
                )
                await send_log(
                    "INFO",
                    "request.end",
                    metadata={"method": method, "path": path, "status_code": status_code, "duration_ms": round(duration_ms, 2)},
                )
            except Exception:
                pass
            # Always clear correlation id after request scope
            clear_correlation_id()

        # Ensure response carries correlation id
        response.headers["X-Correlation-ID"] = current_cid
        return response
