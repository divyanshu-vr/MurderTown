"""Structured logs: one JSON object per line, bound with the game, Day, Phase and Resident.

The orchestrator binds the game and the moment as it plays, and each decision
binds its Resident, so every line says what it is about and logs can be
filtered by any of them. Concurrent decisions run in their own tasks, so one
Resident's binding never leaks into another's lines.
"""

import logging
import sys
from typing import TextIO

import structlog


def configure_logging(stream: TextIO = sys.stderr, level: int = logging.INFO) -> None:
    """Send structured logs to `stream` as JSON lines."""
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.format_exc_info,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            structlog.processors.JSONRenderer(sort_keys=True),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(level),
        logger_factory=structlog.PrintLoggerFactory(stream),
        cache_logger_on_first_use=False,
    )
