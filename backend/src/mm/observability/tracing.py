"""Tracing with OpenTelemetry, shaped for Langfuse: a game is a session, a decision is a
trace, and a model attempt is a generation inside it.

This is the only module that knows about exporters. Traces go to Langfuse when its
keys are set, to any OTLP endpoint (a local Jaeger, say) when one is set, to the
console when asked, and nowhere otherwise. Langfuse wants its session id on every
span, so the game's attributes travel as OpenTelemetry baggage and a span processor
copies them onto each span as it starts.

Attribute names follow Langfuse's OpenTelemetry mapping:
https://langfuse.com/integrations/native/opentelemetry
"""

import base64
from collections.abc import Iterator, Sequence
from contextlib import AbstractContextManager, contextmanager
from dataclasses import dataclass, field

from opentelemetry import baggage, context, trace
from opentelemetry.context import Context
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.trace import ReadableSpan, Span, SpanProcessor, TracerProvider
from opentelemetry.sdk.trace.export import (
    BatchSpanProcessor,
    ConsoleSpanExporter,
    SimpleSpanProcessor,
    SpanExporter,
)
from opentelemetry.util.types import Attributes
from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

SESSION = "langfuse.session.id"
USER = "langfuse.user.id"
TRACE_NAME = "langfuse.trace.name"
TAGS = "langfuse.trace.tags"
OBSERVATION_TYPE = "langfuse.observation.type"
MODEL = "langfuse.observation.model.name"
INPUT = "langfuse.observation.input"
OUTPUT = "langfuse.observation.output"
USAGE = "langfuse.observation.usage_details"
"""A JSON object of exclusive token counts: input, output, cache_read_input_tokens, ..."""
COST = "langfuse.observation.cost_details"
LEVEL = "langfuse.observation.level"
STATUS = "langfuse.observation.status_message"
METADATA = "langfuse.observation.metadata."
"""A prefix: each metadata key becomes its own filterable attribute."""
GAME_SEED = "mm.game.seed"


class TracingSettings(BaseSettings):
    """Where traces go. Secrets come only from the environment (or a local .env file)."""

    model_config = SettingsConfigDict(env_prefix="MM_", env_file=".env", extra="ignore")

    langfuse_public_key: str | None = None
    langfuse_secret_key: SecretStr | None = None
    langfuse_host: str = "https://cloud.langfuse.com"
    otlp_endpoint: str | None = None
    """Any other OTLP/HTTP traces endpoint, e.g. a local Jaeger: http://localhost:4318/v1/traces"""
    trace_console: bool = False


class GameAttributes(SpanProcessor):
    """Copies the game's baggage onto every span as it starts, so each one carries the session."""

    def on_start(self, span: Span, parent_context: Context | None = None) -> None:
        for key, value in baggage.get_all(parent_context).items():
            span.set_attribute(key, str(value))

    def on_end(self, span: ReadableSpan) -> None:
        pass


@dataclass
class _InUse:
    """The provider every span comes from: none until tracing is configured or a test picks one."""

    provider: trace.TracerProvider = field(default_factory=trace.NoOpTracerProvider)


_in_use = _InUse()


def configure_tracing(settings: TracingSettings) -> None:
    """Send traces wherever the settings say; with nothing configured, tracing stays off."""
    exporters = _exporters(settings)
    if exporters:
        use(tracer_provider(exporters))


def tracer_provider(exporters: Sequence[SpanExporter], batch: bool = True) -> TracerProvider:
    """A provider that labels every span with the game and sends it to each exporter."""
    provider = TracerProvider()
    provider.add_span_processor(GameAttributes())
    for exporter in exporters:
        processor = BatchSpanProcessor(exporter) if batch else SimpleSpanProcessor(exporter)
        provider.add_span_processor(processor)
    return provider


def use(provider: trace.TracerProvider) -> None:
    """Make `provider` the one every span comes from. Tests pass one with an in-memory exporter."""
    _in_use.provider = provider


def tracer() -> trace.Tracer:
    return _in_use.provider.get_tracer("mm")


def shutdown_tracing() -> None:
    """Send any spans still waiting, before the process exits."""
    if isinstance(_in_use.provider, TracerProvider):
        _in_use.provider.shutdown()


def game_context(game_id: str, seed: int) -> Context:
    """A context with no span in it, carrying the game as baggage. Each decision's trace
    starts from it, so traces are separate but all belong to the game's session."""
    with_session = baggage.set_baggage(SESSION, game_id, context=Context())
    return baggage.set_baggage(GAME_SEED, str(seed), context=with_session)


@contextmanager
def in_game(game_id: str, seed: int) -> Iterator[None]:
    """Everything traced inside belongs to the game's session."""
    token = context.attach(game_context(game_id, seed))
    try:
        yield
    finally:
        context.detach(token)


def new_trace(name: str, attributes: Attributes) -> AbstractContextManager[trace.Span]:
    """A span that starts a trace of its own, still within the game's session."""
    root = trace.set_span_in_context(trace.INVALID_SPAN)
    return tracer().start_as_current_span(name, context=root, attributes=attributes)


def trace_id_of(span: trace.Span) -> str | None:
    """The span's trace id as Langfuse writes it (32 hex characters), or None when not tracing."""
    found = span.get_span_context()
    return format(found.trace_id, "032x") if found.is_valid else None


def _exporters(settings: TracingSettings) -> list[SpanExporter]:
    exporters: list[SpanExporter] = []
    if settings.langfuse_public_key and settings.langfuse_secret_key:
        secret = settings.langfuse_secret_key.get_secret_value()
        login = base64.b64encode(f"{settings.langfuse_public_key}:{secret}".encode()).decode()
        exporters.append(
            OTLPSpanExporter(
                endpoint=f"{settings.langfuse_host.rstrip('/')}/api/public/otel/v1/traces",
                headers={
                    "Authorization": f"Basic {login}",
                    "x-langfuse-ingestion-version": "4",  # real-time ingestion
                },
            )
        )
    if settings.otlp_endpoint:
        exporters.append(OTLPSpanExporter(endpoint=settings.otlp_endpoint))
    if settings.trace_console:
        exporters.append(ConsoleSpanExporter())
    return exporters
