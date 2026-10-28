"""Observability: structured logs and OpenTelemetry tracing.

Only this package configures where logs and traces go; everything else just logs
with structlog and opens spans with `tracing.tracer()`.
"""
