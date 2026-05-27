from __future__ import annotations

import json
import logging
import re
import time
from collections.abc import Mapping
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

SENSITIVE_KEY_PARTS = (
    "authorization",
    "body",
    "guid",
    "imei",
    "key",
    "protectedkey",
    "secret",
    "service_role",
    "token",
)

_SENSITIVE_TEXT_PATTERNS = (
    re.compile(r"bot\d+:[A-Za-z0-9_-]+"),
    re.compile(r"sb_secret_[A-Za-z0-9_-]+"),
    re.compile(r"sb_publishable_[A-Za-z0-9_-]+"),
)


def sanitize_text(value: str) -> str:
    sanitized = value
    for pattern in _SENSITIVE_TEXT_PATTERNS:
        sanitized = pattern.sub("[REDACTED]", sanitized)
    return sanitized


def sanitize_value(key: str, value: Any) -> Any:
    normalized = key.lower().replace("-", "_")
    if any(part in normalized for part in SENSITIVE_KEY_PARTS):
        return "[REDACTED]"
    if isinstance(value, Mapping):
        return sanitize_mapping(value)
    if isinstance(value, list):
        return [sanitize_value(key, item) for item in value]
    return value


def sanitize_mapping(values: Mapping[str, Any]) -> dict[str, Any]:
    return {key: sanitize_value(key, value) for key, value in values.items()}


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": sanitize_text(record.getMessage()),
        }

        for key, value in record.__dict__.items():
            if key.startswith("_") or key in _STANDARD_LOG_RECORD_KEYS:
                continue
            payload[key] = sanitize_value(key, value)

        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)

        return json.dumps(payload, sort_keys=True, separators=(",", ":"))


_STANDARD_LOG_RECORD_KEYS = set(logging.makeLogRecord({}).__dict__)


def configure_logging(level: str) -> None:
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(level.upper())
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:  # type: ignore[no-untyped-def]
        request_id = request.headers.get("X-Request-ID", str(uuid4()))
        request.state.request_id = request_id
        started = time.perf_counter()
        logger = logging.getLogger("ota_backend.request")
        status_code = 500
        try:
            response = await call_next(request)
            status_code = response.status_code
            return response
        finally:
            duration_ms = int((time.perf_counter() - started) * 1000)
            logger.info(
                "request_complete",
                extra={
                    "request_id": request_id,
                    "action": "http_request",
                    "method": request.method,
                    "path": request.url.path,
                    "status_code": status_code,
                    "duration_ms": duration_ms,
                },
            )
