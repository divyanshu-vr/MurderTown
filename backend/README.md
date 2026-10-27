# MurderTown backend

Python 3.12, managed with [uv](https://docs.astral.sh/uv/).

```
uv sync                  # install
uv run mm play           # play a scripted game in the terminal
uv run mm serve          # run the API on http://127.0.0.1:8000
uv run mm new-game       # start a game on the running API and print where to watch it
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

- **`mm.engine`**: the rules. Events and who may perceive them, the state fold, casting, the Vote and win conditions. No I/O, clocks or async, so every rule is a plain function you can read and test.
- **`mm.agents`**: decision sources. The `Brain` interface, and scripted bots that play legally without a model.
- **`mm.orchestrator`**: runs a game. One module per Phase, the event log and the `Game` that asks Residents for decisions.
- **`mm.persistence`**: the game store (SQLAlchemy, migrations with Alembic) and the in-process live bus.
- **`mm.api`**: FastAPI. Starts games in the background and serves their logs over REST and WebSocket.
- **`mm.cli`**: the `mm` command.
