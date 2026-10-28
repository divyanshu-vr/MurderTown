"""Fixtures and helpers shared by the transport tests, which drive the API like a browser would."""

import os
import time
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from mm.api import Settings, create_app


@pytest.fixture
def database_url(tmp_path: Path) -> str:
    """A fresh SQLite file, or the database named by MM_TEST_DATABASE_URL (e.g. Docker Postgres)."""
    sqlite_file = (tmp_path / "murdertown.sqlite3").as_posix()
    return os.environ.get("MM_TEST_DATABASE_URL", f"sqlite+aiosqlite:///{sqlite_file}")


@pytest.fixture
def client(database_url: str) -> Iterator[TestClient]:
    with TestClient(create_app(Settings(database_url=database_url))) as test_client:
        yield test_client


def start_game(client: TestClient, config: dict[str, Any]) -> str:
    response = client.post("/games", json=config)
    assert response.status_code == 201
    game_id: str = response.json()["id"]
    return game_id


def wait_until_finished(client: TestClient, game_id: str) -> None:
    deadline = time.monotonic() + 20
    while client.get(f"/games/{game_id}").json()["status"] == "running":
        assert time.monotonic() < deadline, "the game never finished"
        time.sleep(0.02)
