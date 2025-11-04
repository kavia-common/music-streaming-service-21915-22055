"""
Structured logging utilities for BackendAPI with correlation IDs.

Provides:
- get_logger: JSON-like structured logger
- correlation ID management for per-request tracing via contextvars
"""

from __future__ import annotations

import json
import logging
import sys
import uuid
from contextvars import ContextVar
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from src.core.config import get_settings

# Context variable to hold correlation ID per request
_cid_ctx: ContextVar[Optional[str]] = ContextVar("correlation_id", default=None)


class JsonFormatter(logging.Formatter):
    """Logging Formatter to output JSON structured logs."""

    def format(self, record: logging.LogRecord) -> str:
        settings = get_settings()
        base: Dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "message": record.getMessage(),
            "logger": record.name,
            "service": settings.OBS_SERVICE_NAME,
            "environment": settings.OBS_ENVIRONMENT,
        }

        # correlation id (trace/reference id) if present
        cid = get_correlation_id()
        if cid:
            base["correlation_id"] = cid

        # Include extra fields passed via logger extra
        if record.args and isinstance(record.args, dict):
            for k, v in record.args.items():
                if k not in base:
                    base[k] = v

        # Attach exception info if any
        if record.exc_info:
            base["exc_info"] = self.formatException(record.exc_info)

        return json.dumps(base, ensure_ascii=False)


def _configure_root_logger() -> None:
    """Configure root logger once."""
    root = logging.getLogger()
    if getattr(root, "_backendapi_observed", False):
        return
    root.setLevel(logging.INFO)
    handler = logging.StreamHandler(stream=sys.stdout)
    handler.setFormatter(JsonFormatter())
    root.handlers = [handler]
    setattr(root, "_backendapi_observed", True)


# PUBLIC_INTERFACE
def get_logger(name: str = "backendapi") -> logging.Logger:
    """Get a structured logger configured for BackendAPI."""
    _configure_root_logger()
    return logging.getLogger(name)


# PUBLIC_INTERFACE
def set_correlation_id(correlation_id: Optional[str]) -> str:
    """Set the current correlation ID in context, generating one if missing.

    Returns the correlation id that is set.
    """
    if not correlation_id:
        correlation_id = str(uuid.uuid4())
    _cid_ctx.set(correlation_id)
    return correlation_id


# PUBLIC_INTERFACE
def get_correlation_id() -> Optional[str]:
    """Get the current correlation ID from context if set."""
    return _cid_ctx.get()


# PUBLIC_INTERFACE
def clear_correlation_id() -> None:
    """Clear correlation ID from context (set to None)."""
    _cid_ctx.set(None)
