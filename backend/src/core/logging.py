"""
Structured logging setup using structlog.

Provides:
- configure_logging()  – called once at application startup
- get_logger()         – returns a bound structlog logger for a named module
- LogContext           – dataclass holding per-request context fields
- set_log_context()    – stores context in contextvars so every downstream
                         log call within the same async task picks it up
"""
from __future__ import annotations

import logging
import sys
from contextvars import ContextVar
from dataclasses import dataclass, field
from typing import Optional

import structlog

# ---------------------------------------------------------------------------
# Context variables – stored per-async-task (coroutine / thread)
# ---------------------------------------------------------------------------

_request_id_var: ContextVar[str] = ContextVar("request_id", default="")
_user_id_var: ContextVar[str] = ContextVar("user_id", default="")
_tenant_id_var: ContextVar[str] = ContextVar("tenant_id", default="")


# ---------------------------------------------------------------------------
# Public dataclass
# ---------------------------------------------------------------------------


@dataclass
class LogContext:
    """Snapshot of the current structured logging context."""

    request_id: str = field(default="")
    user_id: Optional[str] = field(default=None)
    tenant_id: Optional[str] = field(default=None)


# ---------------------------------------------------------------------------
# Public helpers
# ---------------------------------------------------------------------------


def set_log_context(
    request_id: str,
    user_id: Optional[str] = None,
    tenant_id: Optional[str] = None,
) -> None:
    """
    Bind per-request context into contextvars.

    Call this early in a request lifecycle (e.g. a FastAPI middleware) so
    that every log statement issued during that request automatically
    includes these fields.
    """
    _request_id_var.set(request_id)
    _user_id_var.set(user_id or "")
    _tenant_id_var.set(tenant_id or "")


def _add_context_fields(
    logger: object,  # noqa: ARG001
    method_name: str,  # noqa: ARG001
    event_dict: structlog.types.EventDict,
) -> structlog.types.EventDict:
    """structlog processor that injects contextvar values into every log record."""
    request_id = _request_id_var.get("")
    user_id = _user_id_var.get("")
    tenant_id = _tenant_id_var.get("")

    if request_id:
        event_dict["request_id"] = request_id
    if user_id:
        event_dict["user_id"] = user_id
    if tenant_id:
        event_dict["tenant_id"] = tenant_id

    return event_dict


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------


def configure_logging(log_level: str = "INFO", is_production: bool = False) -> None:
    """
    Configure both structlog and the standard-library logging integration.

    Parameters
    ----------
    log_level:
        One of DEBUG, INFO, WARNING, ERROR, CRITICAL.
    is_production:
        When *True* emit newline-delimited JSON (stdout).
        When *False* emit colourised, human-readable output.
    """
    level = getattr(logging, log_level.upper(), logging.INFO)

    # --- Standard library root logger ---
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=level,
    )

    # Silence noisy third-party loggers in production
    for noisy in ("uvicorn.access", "sqlalchemy.engine", "httpcore", "httpx"):
        logging.getLogger(noisy).setLevel(logging.WARNING)

    # --- Shared processors ---
    shared_processors: list[structlog.types.Processor] = [
        structlog.contextvars.merge_contextvars,
        _add_context_fields,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
    ]

    if is_production:
        # JSON output – machine-parseable
        renderer: structlog.types.Processor = structlog.processors.JSONRenderer()
    else:
        # Pretty output – human-readable in development
        shared_processors.append(structlog.processors.ExceptionRenderer())
        renderer = structlog.dev.ConsoleRenderer(colors=True)

    structlog.configure(
        processors=[
            *shared_processors,
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    formatter = structlog.stdlib.ProcessorFormatter(
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            renderer,
        ],
        foreign_pre_chain=shared_processors,
    )

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    root = logging.getLogger()
    # Remove any handlers added by basicConfig, replace with ours
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(level)


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    """
    Return a structlog logger bound to *name*.

    Usage::

        log = get_logger(__name__)
        log.info("user_created", user_id="abc123")
    """
    return structlog.get_logger(name)
