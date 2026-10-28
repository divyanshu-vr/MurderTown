# mm.persistence: storage and live delivery

Owns where games are kept and how new events reach watchers.

**May import:** the layers below it (`mm.orchestrator`, `mm.agents`, `mm.engine`). It needs `mm.engine` and, for model calls, `mm.agents`.

**Entry points**
- `store.py`: `GameStore`, which creates games, appends events, records how a game ended, pages a game's events after a sequence number, and keeps model calls: `record_call`, `calls(decision_id)` and `caused_by(decision_id)` serve the explain endpoint.
- `database.py`: `open_database(url)`, which opens Postgres or SQLite; SQLite runs in WAL mode so writing an event per row stays fast.
- `tables.py` and `migrations/`: the `games`, `events` and `model_calls` tables. Events and model calls are never changed after they are written. `migrate.upgrade(engine)` brings any database (SQLite in tests, Postgres in development and production) to the latest schema.
- `bus.py`: the `Bus` interface and `InProcessBus`, which fan a game's new events out to everyone watching it.

**Why it is shaped this way:** the store is the source of truth and the bus only carries news, so a watcher who reads the stored backlog and then follows the bus can never miss an event. The bus is an interface because a Redis-backed one will replace the in-memory bus when the API runs on several workers.
