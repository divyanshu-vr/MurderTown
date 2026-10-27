"""Seam 1: properties that hold for every game, whatever the configuration and seed."""

import asyncio
from collections.abc import Sequence
from itertools import pairwise

from hypothesis import given, settings
from hypothesis import strategies as st

from mm.agents import Brain, scripted_bots
from mm.engine import GameConfig, Resident
from mm.engine.decisions import SKIP, Decision, DecisionRequest
from mm.engine.events import BallotCast, Event, GameEnded
from mm.engine.state import GameState
from mm.orchestrator import GameResult, play_game


@st.composite
def game_configs(draw: st.DrawFn) -> GameConfig:
    residents = draw(st.integers(6, 15))
    return GameConfig(
        residents=residents,
        murderers=draw(st.integers(1, residents // 4)),
        doctor=draw(st.booleans()),
        detective=draw(st.booleans()),
        sheriff=draw(st.booleans()),
        max_days=draw(st.integers(1, 10)),
        seed=draw(st.integers(0, 2**32 - 1)),
    )


class Watched:
    """Wraps a decision source and records whether its Resident was alive when asked."""

    def __init__(self, inner: Brain, asked_while_dead: list[str]) -> None:
        self.inner, self.asked_while_dead = inner, asked_while_dead

    async def decide(self, request: DecisionRequest, view: Sequence[Event]) -> Decision:
        if request.resident in GameState.fold(view).dead:
            self.asked_while_dead.append(request.resident)
        return await self.inner.decide(request, view)


def play_watched(config: GameConfig) -> tuple[GameResult, list[str]]:
    asked_while_dead: list[str] = []
    bots = scripted_bots(config.seed)

    def make(resident: Resident) -> Brain:
        return Watched(bots(resident), asked_while_dead)

    return asyncio.run(play_game(config, make)), asked_while_dead


@settings(max_examples=60, deadline=None)
@given(game_configs())
def test_every_game_obeys_the_invariants(config: GameConfig) -> None:
    result, asked_while_dead = play_watched(config)
    events = result.events

    assert [event.seq for event in events] == list(range(1, len(events) + 1))

    endings = [i for i, event in enumerate(events) if isinstance(event.payload, GameEnded)]
    assert endings == [len(events) - 1]

    state, living_counts = GameState(), []
    for event in events:
        if isinstance(event.payload, BallotCast):
            assert event.payload.voter in state.living
            assert event.payload.choice in {*state.living, SKIP} - {event.payload.voter}
        state.apply(event.payload)
        living_counts.append(len(state.living))
    after_casting = living_counts[1:]
    assert all(before >= after for before, after in pairwise(after_casting))

    assert asked_while_dead == []
