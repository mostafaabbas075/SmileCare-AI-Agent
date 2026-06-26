"""
Structured logging setup.

Uses ``structlog`` to produce JSON-formatted log records in production and
pretty human-readable output in development. Every log entry automatically
includes:

  - timestamp (ISO-8601)
  - log level
  - logger name
  - caller location (module + line)

Usage::

    import structlog

    logger = structlog.get_logger(__name__)
    logger.info("patient_created", patient_id=str(patient.id))
"""

from __future__ import annotations

import logging
import sys
from typing import Any

import structlog
from structlog.types import EventDict, Processor

from app.core.config import settings


def _add_caller_info(
    logger: logging.Logger,
    method_name: str,
    event_dict: EventDict,
) -> EventDict:
    """Add module and line number to every log record."""
    record = event_dict.get("_record")
    if record is not None:
        event_dict["module"] = record.module
        event_dict["lineno"] = record.lineno
    return event_dict


def setup_logging() -> None:
    """Configure structlog and the stdlib logging bridge.

    Call this exactly once at application startup (inside ``lifespan`` in
    ``main.py``).
    """
    shared_processors: list[Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.StackInfoRenderer(),
    ]

    if settings.is_production:
        # JSON output for log aggregation (Datadog, Loki, CloudWatch, etc.)
        renderer: Processor = structlog.processors.JSONRenderer()
    else:
        # Human-friendly coloured output for local development
        renderer = structlog.dev.ConsoleRenderer(colors=True)

    structlog.configure(
        processors=[
            *shared_processors,
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        wrapper_class=structlog.make_filtering_bound_logger(
            logging.getLevelName(settings.log_level)
        ),
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    formatter = structlog.stdlib.ProcessorFormatter(
        foreign_pre_chain=shared_processors,
        processors=[
            _add_caller_info,
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            renderer,
        ],
    )

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.handlers = [handler]
    root_logger.setLevel(settings.log_level)

    # Suppress noisy third-party loggers
    for noisy in ("uvicorn.access", "sqlalchemy.engine", "httpx"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
