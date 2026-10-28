"""Fixtures and helpers shared by the tests: quiet logs, and the API driven like a browser would."""

import asyncio
import io
import logging
import os
import time
from collections.abc import Callable, Iterator, Mapping
from contextlib import contextmanager
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from mm.api import Settings, create_app
from mm.api.live_games import BrainsFor
from mm.llm import ModelProvider
from mm.observability.logs import configure_logging
from mm.persistence import open_database


@pytest.fixture(autouse=True, scope="session")
def quiet_logs() -> None:
    """Tests keep logs out of their output; a test that reads logs sends them elsewhere."""
    configure_logging(io.StringIO(), level=logging.CRITICAL)


@pytest.fixture
def database_url(tmp_path: Path) -> str:
    """A fresh SQLite file, or the database named by MM_TEST_DATABASE_URL (e.g. Docker Postgres),
    emptied first: a game an earlier test left running would otherwise resume in this one."""
    shared = os.environ.get("MM_TEST_DATABASE_URL")
    if shared is None:
        return f"sqlite+aiosqlite:///{(tmp_path / 'murdertown.sqlite3').as_posix()}"
    asyncio.run(emptied(shared))
    return shared


async def emptied(url: str) -> None:
    engine = open_database(url)
    async with engine.begin() as connection:
        if await connection.scalar(text("SELECT to_regclass('games')")) is not None:
            await connection.execute(text("TRUNCATE model_calls, events, games"))
    await engine.dispose()


@contextmanager
def serving(
    database_url: str,
    brains_for: BrainsFor | None = None,
    providers: Mapping[str, ModelProvider] | None = None,
    **settings: Any,
) -> Iterator[TestClient]:
    """The API on its own database, with Residents played by `brains_for`, or as each game's
    lineup says on `providers` (no API keys: a game the lineup puts on a model is refused).
    Leaving the block shuts the server down, as stopping `mm serve` would."""
    app = create_app(
        Settings(database_url=database_url, **settings),
        brains_for=brains_for,
        providers=providers if providers is not None else {},
    )
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def client(database_url: str) -> Iterator[TestClient]:
    with serving(database_url) as test_client:
        yield test_client


def start_game(client: TestClient, config: dict[str, Any]) -> str:
    response = client.post("/games", json=config)
    assert response.status_code == 201
    game_id: str = response.json()["id"]
    return game_id


def wait_until(condition: Callable[[], bool], what: str, seconds: float = 20) -> None:
    deadline = time.monotonic() + seconds
    while not condition():
        assert time.monotonic() < deadline, f"never {what}"
        time.sleep(0.02)


def wait_until_finished(client: TestClient, game_id: str) -> None:
    wait_until(lambda: client.get(f"/games/{game_id}").json()["status"] != "running", "finished")
