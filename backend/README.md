# MurderTown backend

Python 3.12, managed with [uv](https://docs.astral.sh/uv/).

```
uv sync                  # install
uv run mm play           # play a scripted game in the terminal
uv run mm play --provider claude --residents 6 --max-days 1   # a short live game on your Claude subscription
uv run mm serve          # run the API on http://127.0.0.1:8000 and print the Host's link
uv run mm new-game       # start a game on the running API, as the Host, and print where to watch it
uv run pytest            # tests
```

Settings come from `MM_*` environment variables or `backend/.env` (see `.env.example`). SQLite works with no setup; for Postgres run `docker compose up -d` at the repo root and point `MM_DATABASE_URL` at port 5433.

## How a game flows through the packages

```
  decision sources (agents)          orchestrator                      engine (pure)
  ScriptedBot / Puppet / Agent  <--  Game asks one Resident  -------->  rules, options
          |                          at a time, or several at once      perceived_by(log)
          +-- decision ------------> checks it (why_illegal)
                                     appends events ------------------> GameState.apply
                                          |
                                          +--> observers: GameStore (persistence), then live Bus
                                                                  |
                                          api: REST pages the store, WebSocket = backlog + bus
```

Each package explains what it owns, what it may import and why it is shaped that way:
[engine](src/mm/engine/README.md), [agents](src/mm/agents/README.md),
[orchestrator](src/mm/orchestrator/README.md), [llm](src/mm/llm/README.md),
[review](src/mm/review/README.md), [persistence](src/mm/persistence/README.md), [api](src/mm/api/README.md) and [cli](src/mm/cli/README.md).
