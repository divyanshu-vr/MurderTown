"""Seam 1 seen through the transport.

A client reading a game over REST or WebSocket must receive exactly the event
log that `play_game` produces for the same configuration: no gaps, no
duplicates, even when it disconnects and reconnects while the game is running.
"""

import asyncio
from collections.abc import Iterator
from typing import Any

import pytest
from fastapi.testclient import TestClient

from mm.agents import scripted_bots
from mm.engine import GameConfig
from mm.orchestrator import play_game
from tests.conftest import following, serving, start_game, wait_until_finished
from tests.support import unhurried_bots

CONFIG = {"residents": 8, "murderers": 2, "max_days": 4, "seed": 4, "open_floor_seconds": None}


def expected_log() -> list[dict[str, Any]]:
    config = GameConfig(**CONFIG)
    result = asyncio.run(play_game(config, scripted_bots(config.seed)))
    return [event.model_dump(mode="json") for event in result.events]


@pytest.fixture
def slow_client(database_url: str) -> Iterator[TestClient]:
    with serving(database_url, unhurried_bots) as test_client:
        yield test_client


def test_rest_serves_the_whole_log_of_a_finished_game(client: TestClient) -> None:
    game_id = start_game(client, CONFIG)
    wait_until_finished(client, game_id)

    events = client.get(f"/games/{game_id}/events").json()["events"]

    assert events == expected_log()


def test_rest_pages_events_after_a_sequence_number(client: TestClient) -> None:
    game_id = start_game(client, CONFIG)
    wait_until_finished(client, game_id)

    page = client.get(f"/games/{game_id}/events", params={"after": 10, "limit": 5}).json()

    assert [event["seq"] for event in page["events"]] == [11, 12, 13, 14, 15]


def test_a_reconnecting_websocket_client_receives_the_log_without_gaps_or_duplicates(
    slow_client: TestClient,
) -> None:
    game_id = start_game(slow_client, CONFIG)
    received: list[dict[str, Any]] = []

    with following(slow_client, game_id) as socket:
        received += [socket.receive_json() for _ in range(25)]
    assert slow_client.get(f"/games/{game_id}").json()["status"] == "running"

    with following(slow_client, game_id, after=received[-1]["seq"]) as socket:
        while not received or received[-1]["payload"]["type"] != "game_ended":
            received.append(socket.receive_json())

    assert received == expected_log()
