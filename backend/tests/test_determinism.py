"""Seam 1: a game is fully determined by its configuration and its Residents' decisions."""

from mm.agents import scripted_bots
from mm.engine import GameConfig, Role
from mm.engine.events import Event, GameStarted, RoleAssigned
from mm.engine.state import GameState
from mm.orchestrator import play_game
from tests.support import payloads


async def test_the_same_seed_and_decisions_produce_an_identical_event_log() -> None:
    config = GameConfig(seed=42)

    first = await play_game(config, scripted_bots(seed=42))
    second = await play_game(config, scripted_bots(seed=42))

    assert [e.model_dump() for e in first.events] == [e.model_dump() for e in second.events]


async def test_a_different_seed_casts_a_different_town() -> None:
    def town(events: list[Event]) -> tuple[tuple[str, Role], ...]:
        (started,) = payloads(events, GameStarted)
        roles = {a.resident: a.role for a in payloads(events, RoleAssigned)}
        return tuple((r.name, roles[r.name]) for r in started.residents)

    first = await play_game(GameConfig(seed=1, max_days=2), scripted_bots(seed=1))
    second = await play_game(GameConfig(seed=2, max_days=2), scripted_bots(seed=2))

    assert town(first.events) != town(second.events)


async def test_folding_the_log_reproduces_the_runners_final_state() -> None:
    result = await play_game(GameConfig(seed=9), scripted_bots(seed=9))

    assert GameState.fold(result.events) == result.state
