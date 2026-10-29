"""Logs are JSON lines that say which game, Day, Phase and Resident they are about."""

import io
import json
import logging
from collections.abc import Iterator
from typing import Any

import pytest

from mm.agents import ModelCall, llm_agents
from mm.engine import GameConfig, PlayedBy
from mm.observability.logs import configure_logging
from mm.orchestrator import play_game
from tests.support import FakeModel

CONFIG = GameConfig(residents=6, murderers=1, max_days=2, seed=13)


@pytest.fixture
def logged() -> Iterator[io.StringIO]:
    stream = io.StringIO()
    configure_logging(stream)
    yield stream
    configure_logging(io.StringIO(), level=logging.CRITICAL)


async def test_every_line_says_which_game_day_phase_and_resident_it_is_about(
    logged: io.StringIO,
) -> None:
    async def record(call: ModelCall) -> None:
        pass

    agents = llm_agents(FakeModel(), PlayedBy(), record, CONFIG.seed)
    await play_game(CONFIG, agents, game_id="game-one")

    lines: list[dict[str, Any]] = [json.loads(line) for line in logged.getvalue().splitlines()]
    calls = [line for line in lines if line["event"] == "model call"]
    assert calls
    assert all({"game", "day", "phase", "resident", "decision"} <= set(line) for line in calls)
    assert {line["game"] for line in lines} == {"game-one"}
    starts = {(line["day"], line["phase"]) for line in lines if line["event"] == "phase started"}
    assert {(1, "night"), (2, "dawn"), (2, "vote"), (2, "dusk"), (2, "night")} <= starts
    statements = [line for line in calls if line["kind"] == "statement"]
    assert len({line["resident"] for line in statements}) == CONFIG.residents - 1  # one murdered
