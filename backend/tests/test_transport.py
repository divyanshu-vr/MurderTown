"""Seam 1 seen through the transport.

A client reading a game over REST or WebSocket must receive exactly the event
log that `play_game` produces for the same configuration: no gaps, no
duplicates, even when it disconnects and reconnects while the game is running.
"""

import asyncio
import os
import time
from collections.abc import Iterator, Sequence
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from mm.agents import Brain, BrainFactory, scripted_bots
from mm.api import Settings, create_app
from mm.engine import GameConfig
from mm.engine.decisions import Answer, DecisionRequest
from mm.engine.events import Event
from mm.orchestrator import play_game
from tests.support import wrapped

CONFIG = {"residents": 8, "murderers": 2, "max_days": 4, "seed": 4}


def expected_log() -> list[dict[str, Any]]:
    config = GameConfig(**CONFIG)
    result = asyncio.run(play_game(config, scripted_bots(config.seed)))
    return [event.model_dump(mode="json") for event in result.events]


class Unhurried:
    """A scripted bot that takes a moment to think, so the game is still live while we watch."""

    def __init__(self, inner: Brain) -> None:
        self.inner = inner

    async def decide(self, request: DecisionRequest, view: Sequence[Event]) -> Answer:
        await asyncio.sleep(0.005)
        return await self.inner.decide(request, view)


def unhurried_bots(config: GameConfig) -> BrainFactory:
    return wrapped(scripted_bots(config.seed), Unhurried)


@pytest.fixture
def database_url(tmp_path: Path) -> str:
    """A fresh SQLite file, or the database named by MM_TEST_DATABASE_URL (e.g. Docker Postgres)."""
    sqlite_file = (tmp_path / "murdertown.sqlite3").as_posix()
    return os.environ.get("MM_TEST_DATABASE_URL", f"sqlite+aiosqlite:///{sqlite_file}")


@pytest.fixture
def client(database_url: str) -> Iterator[TestClient]:
    with TestClient(create_app(Settings(database_url=database_url))) as test_client:
        yield test_client


@pytest.fixture
def slow_client(database_url: str) -> Iterator[TestClient]:
    app = create_app(Settings(database_url=database_url), brains_for=unhurried_bots)
    with TestClient(app) as test_client:
        yield test_client


def start_game(client: TestClient) -> str:
    response = client.post("/games", json=CONFIG)
    assert response.status_code == 201
    game_id: str = response.json()["id"]
    return game_id


def wait_until_finished(client: TestClient, game_id: str) -> None:
    deadline = time.monotonic() + 20
    while client.get(f"/games/{game_id}").json()["status"] == "running":
        assert time.monotonic() < deadline, "the game never finished"
        time.sleep(0.02)


def test_rest_serves_the_whole_log_of_a_finished_game(client: TestClient) -> None:
    game_id = start_game(client)
    wait_until_finished(client, game_id)

    events = client.get(f"/games/{game_id}/events").json()["events"]

    assert events == expected_log()


def test_rest_pages_events_after_a_sequence_number(client: TestClient) -> None:
    game_id = start_game(client)
    wait_until_finished(client, game_id)

    page = client.get(f"/games/{game_id}/events", params={"after": 10, "limit": 5}).json()

    assert [event["seq"] for event in page["events"]] == [11, 12, 13, 14, 15]


def test_a_reconnecting_websocket_client_receives_the_log_without_gaps_or_duplicates(
    slow_client: TestClient,
) -> None:
    game_id = start_game(slow_client)
    received: list[dict[str, Any]] = []

    with slow_client.websocket_connect(f"/ws/games/{game_id}?after=0") as socket:
        received += [socket.receive_json() for _ in range(25)]
    assert slow_client.get(f"/games/{game_id}").json()["status"] == "running"

    with slow_client.websocket_connect(
        f"/ws/games/{game_id}?after={received[-1]['seq']}"
    ) as socket:
        while not received or received[-1]["payload"]["type"] != "game_ended":
            received.append(socket.receive_json())

    assert received == expected_log()
