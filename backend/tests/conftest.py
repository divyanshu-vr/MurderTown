"""Fixtures and helpers shared by the tests: quiet logs, the API driven like a browser would, and
a served game played by Agents whose model calls are recorded."""

import asyncio
import io
import json
import logging
import os
import time
from collections.abc import Callable, Iterator, Mapping, Sequence
from contextlib import contextmanager
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from starlette.testclient import WebSocketTestSession

from mm.agents import BrainFactory, CallRecorder, ModelCall, llm_agents
from mm.api import Settings, create_app
from mm.api.live_games import BrainsFor
from mm.api.routes import HOST_TOKEN_HEADER
from mm.engine import GameConfig, PlayedBy
from mm.engine.decisions import DecisionKind
from mm.llm import ModelProvider, ModelReply, ModelRequest, Usage
from mm.observability.logs import configure_logging
from mm.persistence import open_database
from tests.support import FakeModel, answer_kind, sensible_answer

HOST_TOKEN = "the-host-token-for-tests"


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
    The client acts as the Host, sending the Host token; see `spectating` for everyone else.
    Leaving the block shuts the server down, as stopping `mm serve` would."""
    app = create_app(
        Settings(database_url=database_url, **{"host_token": HOST_TOKEN, **settings}),
        brains_for=brains_for,
        providers=providers if providers is not None else {},
    )
    with TestClient(app, headers={HOST_TOKEN_HEADER: HOST_TOKEN}) as test_client:
        yield test_client


@pytest.fixture
def client(database_url: str) -> Iterator[TestClient]:
    with serving(database_url) as test_client:
        yield test_client


@contextmanager
def spectating(client: TestClient) -> Iterator[TestClient]:
    """The same client without the Host token, as any Spectator's browser would be."""
    token = client.headers.pop(HOST_TOKEN_HEADER)
    try:
        yield client
    finally:
        client.headers[HOST_TOKEN_HEADER] = token


@contextmanager
def following(client: TestClient, game_id: str, after: int = 0) -> Iterator[WebSocketTestSession]:
    """A full-scope socket on a game, opened as the Host's browser opens one: it cannot send
    a header, so it sends the Host token first."""
    with client.websocket_connect(f"/ws/games/{game_id}?after={after}&scope=full") as socket:
        socket.send_text(HOST_TOKEN)
        yield socket


def start_game(client: TestClient, config: dict[str, Any]) -> str:
    response = client.post("/games", json=config)
    assert response.status_code == 201
    game_id: str = response.json()["id"]
    return game_id


def played_to_the_end(client: TestClient, config: dict[str, Any]) -> str:
    """Start a game and wait for it to end."""
    game_id = start_game(client, config)
    wait_until_finished(client, game_id)
    return game_id


def wait_until(condition: Callable[[], bool], what: str, seconds: float = 20) -> None:
    deadline = time.monotonic() + seconds
    while not condition():
        assert time.monotonic() < deadline, f"never {what}"
        time.sleep(0.02)


def wait_until_finished(client: TestClient, game_id: str) -> None:
    def over() -> bool:
        return client.get(f"/games/{game_id}").json()["status"] in ("finished", "aborted", "failed")

    wait_until(over, "finished")


# A served game played by Agents, its model calls recorded


def varied_usage(request: ModelRequest) -> ModelReply:
    """Sensible answers whose tokens differ by decision kind, with both kinds of cache write.
    Every first ballot is unusable and every Dusk intent refused, so retries and refusals count."""
    kind = answer_kind(request)
    n = list(DecisionKind).index(kind) + 1
    usage = Usage(
        input_tokens=10 * n,
        output_tokens=3 * n,
        cache_read_tokens=5 * n,
        cache_write_5m_tokens=n % 2,
        cache_write_1h_tokens=2 * n,
    )
    if kind is DecisionKind.DUSK_INTENT:
        return ModelReply(outcome="refusal", data=None, text="", usage=usage, error="declined")
    if kind is DecisionKind.BALLOT and "could not be used" not in request.prompt:
        answer: dict[str, object] = {"target": "Nobody", "reason": "a hunch"}
    else:
        answer = sensible_answer(request).data or {}
    return ModelReply(outcome="ok", data=answer, text=json.dumps(answer), usage=usage)


@pytest.fixture
def recorded(database_url: str) -> Iterator[tuple[TestClient, list[ModelCall]]]:
    """An API whose games are played by Agents, plus every model call they recorded."""
    calls: list[ModelCall] = []

    def agents(
        config: GameConfig, record: CallRecorder, replay: Sequence[ModelCall]
    ) -> BrainFactory:
        async def keep(call: ModelCall) -> None:
            calls.append(call)
            await record(call)

        return llm_agents(FakeModel(varied_usage), PlayedBy(), keep, config.seed)

    with serving(database_url, agents) as client:
        yield client, calls
