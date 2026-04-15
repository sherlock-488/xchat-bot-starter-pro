"""
Structured logging setup using structlog.

Configures a processor chain appropriate for the log format:
  - "console": human-readable colored output for development
  - "json": structured JSON output for production/aggregation

Each log entry includes:
  - timestamp (ISO 8601 UTC)
  - log level
  - logger name
  - request_id (if bound via bind_request_id())
  - all keyword arguments passed to the log call

Usage::

    from xchat_bot.logging.setup import configure_logging, bind_request_id

    configure_logging(log_level="INFO", log_format="console")

    import structlog
    logger = structlog.get_logger(__name__)
    logger.info("event_received", event_type="chat.received", event_id="abc123")
"""

from __future__ import annotations

import logging
import sys
from contextlib import contextmanager
from typing import Generator

import structlog
from structlog.types import EventDict, Processor


def configure_logging(
    log_level: str = "INFO",
    log_format: str = "console",
) -> None:
    """Configure structlog and stdlib logging.

    Call once at application startup.

    Args:
        log_level: Minimum log level (DEBUG, INFO, WARNING, ERROR, CRITICAL).
        log_format: "console" for human-readable, "json" for structured JSON.
    """
    level = getattr(logging, log_level.upper(), logging.INFO)

    shared_processors: list[Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        structlog.processors.StackInfoRenderer(),
    ]

    if log_format == "json":
        renderer: Processor = structlog.processors.JSONRenderer()
    else:
        renderer = structlog.dev.ConsoleRenderer(
            colors=sys.stderr.isatty(),
            exception_formatter=structlog.dev.plain_traceback,
        )

    structlog.configure(
        processors=[
            *shared_processors,
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        wrapper_class=structlog.make_filtering_bound_logger(level),
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    formatter = structlog.stdlib.ProcessorFormatter(
        foreign_pre_chain=shared_processors,
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            renderer,
        ],
    )

    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.addHandler(handler)
    root_logger.setLevel(level)

    # Silence noisy libraries
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)


@contextmanager
def bind_request_id(request_id: str | None = None) -> Generator[str, None, None]:
    """Context manager that binds a request_id to all log entries within scope.

    Args:
        request_id: Optional request ID. If None, a random one is generated.

    Yields:
        The bound request_id.

    Usage::

        with bind_request_id() as rid:
            logger.info("handling_request", path="/webhook")
            # All log entries in this block include request_id=rid
    """
    import secrets
    rid = request_id or secrets.token_hex(8)
    structlog.contextvars.bind_contextvars(request_id=rid)
    try:
        yield rid
    finally:
        structlog.contextvars.unbind_contextvars("request_id")
