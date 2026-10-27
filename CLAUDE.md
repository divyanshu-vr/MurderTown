# MurderTown

A social-deduction game where every Resident is played by an LLM Agent with its own isolated memory, watched by humans in a 2D pixel town. The spec is GitHub issue #1; work is tracked as its sub-issues.

## How the code is shaped

- **The event log is the single source of truth.** True state, each Agent's knowledge, the Spectator view and replays are all folds of one append-only log per game. New behaviour starts as a new event type whose visibility is declared beside its definition (`backend/src/mm/engine/events.py`).
- **Perception has one door**: `perceived_by` in the engine. Everything shown to a Resident (bot view, prompt, inspector) goes through it, which is what makes information isolation testable.
- **Backend layers**, top to bottom: cli, api, persistence, orchestrator, agents, engine. A layer imports only from layers below it (`lint-imports` enforces this). The engine is pure: no I/O, clocks or async.
- **Frontend layers**: `src/core` is pure TypeScript with no React, Phaser or network code (ESLint enforces this); `src/net` talks to the server; `src/ui` renders. Protocol types are generated from the backend, never written by hand.
- **Determinism**: all randomness comes from the game's seeded `Random`. Decisions collected concurrently have their events appended in seat order, so the same seed and decisions always give the same log.
- **Vocabulary** in code, tests and UI text follows `GLOSSARY.md`.

## Changing things

- Work test-first at the agreed seams, asserting only on observable output:
  - **Seam 1**: a decision source per Resident goes in, the event log comes out. Drive it with scripted bots or the `Puppet` test helper.
  - **Transport**: REST and WebSocket deliver exactly that log, including across reconnects.
  - **Seam 3**: a recorded event log goes into the console view. The fixture is `fixtures/scripted-game.ndjson`.
- Adding an event type, a decision kind, a role or a panel: follow `docs/recipes.md`.
- After changing events or API models, regenerate the protocol schema, the shared fixture and the frontend types (commands in `docs/recipes.md`). CI fails on stale copies.
- Before committing, run the checks CI runs (`.github/workflows/ci.yml`).
- One branch per ticket, never commits straight to `main`.

## Gotchas

- On Windows, write multi-line source files with the file tools; long shell heredocs fail to parse.
- If `import mm` fails after adding a package directory, run `uv sync --reinstall-package murdertown` in `backend/`.
- The frontend runs on Node 24, which pnpm downloads per project through `devEngines`; run Node tools through `pnpm`, not the system Node.
- TypeScript stays on 6.0.x until typescript-eslint supports 7.
- The Docker Compose Postgres listens on host port 5433, because a locally installed Postgres may own 5432.

## Agent skills

### Issue tracker

Issues and specs live in GitHub Issues (divyanshu-vr/MurderTown), managed with the `gh` CLI. See `docs/agents/issue-tracker.md`.

### Triage labels

Default vocabulary: `needs-triage`, `needs-info`, `ready-for-agent`, `ready-for-human`, `wontfix`. See `docs/agents/triage-labels.md`.

### Domain docs

Single-context: one `GLOSSARY.md` and `docs/adr/` at the repo root. See `docs/agents/domain.md`.
