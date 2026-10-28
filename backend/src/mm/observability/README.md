# mm.observability: logs and traces

Owns where logs and traces go. Everything else logs with `structlog` and opens spans with `tracing.tracer()`; nothing outside this package imports an exporter.

**May import:** nothing else from `mm`.

**Entry points**
- `__init__.py`: `observed(log_level)`, which a process (`mm play`, the server) wraps itself in: logs and traces from the environment, and spans flushed at the end.
- `logs.py`: `configure_logging(stream, level)`, JSON lines with the game, Day, Phase and Resident bound by the orchestrator, so logs can be filtered by any of them.
- `tracing.py`:
  - `configure_tracing(TracingSettings())` sends spans to Langfuse (when `MM_LANGFUSE_*` keys are set), to any OTLP endpoint such as a local Jaeger (`MM_OTLP_ENDPOINT`), or to the console (`MM_TRACE_CONSOLE`); with none of them, tracing stays off.
  - `in_game` makes everything inside belong to the game's session, carried as baggage that `GameAttributes` copies onto every span.
  - `new_trace` starts a decision's own trace; its labels (who, when, the log position) and tags travel as baggage, so every span of the trace carries them.
  - The attribute names (`SESSION`, `USAGE`, ...) follow Langfuse's OpenTelemetry mapping.

**The shape of a game in Langfuse:** the game is a session; each decision is a trace whose root span is `decision.<kind>` (who decided, the Phase, Day and role); each model attempt is a generation inside it, with the model, the prompt and raw answer, token usage, cost and its attempt number and outcome. Every model-call record keeps its trace id, and the Mind inspector links to it.

**Why it is shaped this way:** Langfuse v4 reads trace-level attributes from each span, not just the root, so the session travels as baggage onto every span. Keeping exporters here means a new backend (another vendor, a file) changes one module.
