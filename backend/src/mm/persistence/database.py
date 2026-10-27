"""Opening the database: Postgres in production, SQLite for local play and tests.

SQLite runs in WAL mode with normal syncing: every event is still durable
against an application crash, without a full disk flush per event, which keeps
games with hundreds of events fast.
"""

from pathlib import Path
from typing import Any

from sqlalchemy import event
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine


def open_database(url: str) -> AsyncEngine:
    parsed = make_url(url)
    engine = create_async_engine(url)
    if parsed.get_backend_name() == "sqlite":
        if parsed.database:
            Path(parsed.database).parent.mkdir(parents=True, exist_ok=True)
        event.listen(engine.sync_engine, "connect", _tune_sqlite)
    return engine


def _tune_sqlite(connection: Any, _record: Any) -> None:
    cursor = connection.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA synchronous=NORMAL")
    cursor.close()
