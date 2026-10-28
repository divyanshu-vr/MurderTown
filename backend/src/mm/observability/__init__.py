"""Observability: structured logs and OpenTelemetry tracing.

Only this package configures where logs and traces go; everything else just logs
with structlog and opens spans with `tracing.tracer()`.
"""

import logging
from collections.abc import Iterator
from contextlib import contextmanager

from mm.observability.logs import configure_logging
from mm.observability.tracing import TracingSettings, configure_tracing, shutdown_tracing


@contextmanager
def observed(log_level: int = logging.INFO) -> Iterator[None]:
    """Configure this process's logs and traces from the environment, and send any
    spans still waiting before the process ends."""
    configure_logging(level=log_level)
    configure_tracing(TracingSettings())
    try:
        yield
    finally:
        shutdown_tracing()
