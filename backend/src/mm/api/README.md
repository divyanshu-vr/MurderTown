# mm.api: the HTTP and WebSocket API

Owns how Spectators and the Host reach games over the network.

**May import:** every layer below it.

**Entry points**
- `app.py`: `create_app(settings, brains_for)` wires the store, the bus and live games together and runs migrations at startup.
- `routes.py`: create a game, read its summary, page its events, and `/ws/games/{id}?after=N`, which sends the backlog after `N` and then every new event until the game ends. For the Mind inspector, `/games/{id}/residents/{name}/mind?at=N` (one Resident's mind as of event `N`) and `/games/{id}/events/{seq}/explain` (the model attempts behind the decision that caused an event). Both need full scope, which `full_scope` alone decides, as does `/games/{id}/cost`, the cost meter's report: each Resident's and the narrator's model calls, and their total. The stream also ends when a game is aborted. Health (`/healthz`) and readiness (`/readyz`) checks.
- `live_games.py`: `LiveGames` runs each game as a background task, storing every event before publishing it and every model call before the event its decision causes. A game whose model gave no answer is marked `aborted`; one that crashed is marked `failed`, and its log still ends with an abort so Spectators see it stop. `BrainsFor(config, record)` chooses the decision sources and hands Agents the recorder.
- `protocol.py`: the protocol as one JSON Schema document, from which the frontend's types are generated.
- `settings.py`: `MM_*` environment settings.

**Why it is shaped this way:** routes only translate between HTTP and the layers below, so every rule stays testable without a network.
