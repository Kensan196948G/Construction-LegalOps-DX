"""Structured logging setup using structlog.

All logs are emitted as JSON on stdout with a stable schema. A
sensitive-data filter strips known PII patterns (My Number, phone,
email) before serialization so that secrets never escape via logs.
"""

from __future__ import annotations

import logging
import sys
from collections.abc import MutableMapping
from contextvars import ContextVar
from typing import Any

import structlog
from structlog.types import EventDict, Processor

from app.core.config import settings

# ----- Request-scoped context -----

_request_id_ctx: ContextVar[str | None] = ContextVar("request_id", default=None)
_user_id_ctx: ContextVar[str | None] = ContextVar("user_id", default=None)


def set_request_context(*, request_id: str | None, user_id: str | None = None) -> None:
    """Bind request-scoped identifiers consumed by structlog processors."""
    _request_id_ctx.set(request_id)
    _user_id_ctx.set(user_id)


def clear_request_context() -> None:
    """Clear request-scoped identifiers (call after each request)."""
    _request_id_ctx.set(None)
    _user_id_ctx.set(None)


def _inject_request_context(
    _logger: Any, _method: str, event_dict: EventDict
) -> EventDict:
    """Inject request_id / user_id into every log event."""
    request_id = _request_id_ctx.get()
    user_id = _user_id_ctx.get()
    if request_id is not None:
        event_dict.setdefault("request_id", request_id)
    if user_id is not None:
        event_dict.setdefault("user_id", user_id)
    return event_dict


# ----- Sensitive-data filter -----

_SENSITIVE_KEYS: frozenset[str] = frozenset(
    {
        "password",
        "passwd",
        "secret",
        "token",
        "access_token",
        "refresh_token",
        "id_token",
        "authorization",
        "api_key",
        "client_secret",
        "jwt",
        "cookie",
        "set-cookie",
        "my_number",
        "mynumber",
        "個人番号",
        "マイナンバー",
    }
)


def _mask_value(value: Any) -> Any:
    """Mask sensitive value while keeping length hint."""
    if value is None:
        return None
    if isinstance(value, str):
        return "***REDACTED***" if value else value
    return "***REDACTED***"


def _redact_mapping(mapping: MutableMapping[str, Any]) -> None:
    """Recursively redact sensitive keys in a mapping (in place)."""
    for key in list(mapping.keys()):
        lowered = key.lower() if isinstance(key, str) else str(key).lower()
        if lowered in _SENSITIVE_KEYS:
            mapping[key] = _mask_value(mapping[key])
            continue
        value = mapping[key]
        if isinstance(value, MutableMapping):
            _redact_mapping(value)
        elif isinstance(value, list):
            for item in value:
                if isinstance(item, MutableMapping):
                    _redact_mapping(item)


def _redact_sensitive(
    _logger: Any, _method: str, event_dict: EventDict
) -> EventDict:
    """Structlog processor that redacts sensitive keys."""
    _redact_mapping(event_dict)
    return event_dict


# ----- Setup -----


def configure_logging() -> None:
    """Configure structlog and the stdlib root logger.

    Idempotent: safe to call multiple times.
    """
    level_name = settings.log_level.upper()
    level = getattr(logging, level_name, logging.INFO)

    # Stdlib root logger: send to stdout, no default formatter (structlog renders).
    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(level)
    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.addHandler(handler)
    root_logger.setLevel(level)

    # Quiet noisy third-party loggers in production.
    for noisy in ("uvicorn.access", "sqlalchemy.engine"):
        logging.getLogger(noisy).setLevel(
            logging.WARNING if settings.is_production else logging.INFO
        )

    processors: list[Processor] = [
        structlog.contextvars.merge_contextvars,
        _inject_request_context,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        _redact_sensitive,
    ]

    if settings.is_development and sys.stdout.isatty():
        processors.append(structlog.dev.ConsoleRenderer(colors=True))
    else:
        processors.append(structlog.processors.JSONRenderer(sort_keys=True))

    structlog.configure(
        processors=processors,
        wrapper_class=structlog.make_filtering_bound_logger(level),
        logger_factory=structlog.PrintLoggerFactory(file=sys.stdout),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str | None = None) -> structlog.stdlib.BoundLogger:
    """Return a structlog bound logger with optional name."""
    return structlog.get_logger(name) if name else structlog.get_logger()


__all__ = [
    "clear_request_context",
    "configure_logging",
    "get_logger",
    "set_request_context",
]
