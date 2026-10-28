# Seeing inside a game: logs and traces

## Logs

`mm serve` writes JSON lines to stderr; `mm play` writes only warnings there, so the transcript on stdout stays readable. Every line carries the `game`, and once play has begun the `day` and `phase`; lines written during a decision also carry the `resident` and the `decision` id. For example, every model call of one Resident:

```
uv run mm serve 2> server.log
jq 'select(.event == "model call" and .resident == "Cora")' server.log
```

## Traces

A game is a **session**, each decision is a **trace** (its root span is `decision.<kind>`), and each model attempt is a **generation** inside it, with the model, the prompt, the raw answer, token usage (input, output, cache read, cache creation), cost, and its attempt number and outcome. Retries and fallbacks show as extra generations marked WARNING or ERROR. Every stored model call keeps its trace id, and the Mind inspector's "why?" drawer links to it.

Tracing is off until you choose where traces go, so tests and quick local games send nothing anywhere. Copy `backend/.env.example` to `backend/.env` and choose Langfuse, a local Jaeger or the console below.

### Langfuse Cloud

1. Create a project at https://cloud.langfuse.com and copy its public and secret API keys into `MM_LANGFUSE_PUBLIC_KEY` and `MM_LANGFUSE_SECRET_KEY` (set `MM_LANGFUSE_HOST` for the US region or a self-hosted Langfuse).
2. To link the inspector to Langfuse, set `VITE_TRACE_URL=https://cloud.langfuse.com/project/<project id>/traces/{traceId}` in `frontend/.env.local`. The project id is in the project's URL.
3. Play a live game: `uv run mm play --brains claude --max-days 1`. Traces arrive in real time (spans are sent with the `x-langfuse-ingestion-version: 4` header).

### Jaeger, locally

```
docker compose --profile tracing up -d
MM_OTLP_ENDPOINT=http://localhost:4318/v1/traces uv run mm play --max-days 1
```

Open http://localhost:16686. Set `VITE_TRACE_URL=http://localhost:16686/trace/{traceId}` to link the inspector to Jaeger.

### The console

`MM_TRACE_CONSOLE=true uv run mm play --max-days 1` prints every span.

## Checked with a live game

On 2026-10-28 a one-Day live game (6 Residents, `claude-haiku-5-5`) was played with the Langfuse keys set, and Langfuse read back through its API:

- the game's 13 decisions were 13 traces, all in the game's one session;
- each trace's root span was its `decision.<kind>` (6 statements, 6 ballots, 1 last words), with the Resident as the user;
- each trace held one generation with the model, prompt and answer, token usage (input, output, cache read, cache creation) and cost, and metadata for the attempt, outcome, role, Phase, Day, decision and log position;
- all 13 stored model calls kept their trace ids.
