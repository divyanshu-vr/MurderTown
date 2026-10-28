"""Seam 1: properties that hold for every game, whatever the configuration and seed."""

import asyncio
from collections import Counter
from collections.abc import Sequence
from itertools import pairwise

from hypothesis import given, settings
from hypothesis import strategies as st

from mm.agents import Brain, scripted_bots
from mm.engine import GameConfig
from mm.engine.decisions import Answer, DecisionRequest
from mm.engine.dusk import APPROACHED_AT_MOST, MESSAGES_PER_CONVERSATION
from mm.engine.events import (
    BallotCast,
    ConversationMessagePosted,
    ConversationStarted,
    Event,
    GameEnded,
)
from mm.engine.state import GameState
from mm.orchestrator import GameResult, play_game
from tests.support import wrapped


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

    async def decide(self, request: DecisionRequest, view: Sequence[Event]) -> Answer:
        if request.resident in GameState.fold(view).dead:
            self.asked_while_dead.append(request.resident)
        return await self.inner.decide(request, view)


def play_watched(config: GameConfig) -> tuple[GameResult, list[str]]:
    asked_while_dead: list[str] = []
    brains = wrapped(scripted_bots(config.seed), lambda bot: Watched(bot, asked_while_dead))
    return asyncio.run(play_game(config, brains)), asked_while_dead


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
            assert event.payload.target in {*state.living, None} - {event.payload.voter}
        state.apply(event.payload)
        living_counts.append(len(state.living))
    after_casting = living_counts[1:]
    assert all(before >= after for before, after in pairwise(after_casting))

    assert asked_while_dead == []
    assert_dusk_keeps_its_limits(events)


def assert_dusk_keeps_its_limits(events: Sequence[Event]) -> None:
    """Per Conversation: at most four messages, taking turns, and only the last ends it.
    Per Day: each Resident asks for at most one Conversation and is approached for at most
    two. Conversations that start together have no Resident in common."""
    started = [e for e in events if isinstance(e.payload, ConversationStarted)]
    asked: Counter[tuple[int, str]] = Counter()
    approached: Counter[tuple[int, str]] = Counter()
    for start in started:
        assert isinstance(start.payload, ConversationStarted)
        pair = set(start.payload.residents)
        messages = [
            e.payload
            for e in events
            if isinstance(e.payload, ConversationMessagePosted)
            and e.day == start.day
            and {e.payload.speaker, e.payload.partner} == pair
        ]
        assert 1 <= len(messages) <= MESSAGES_PER_CONVERSATION
        assert all(a.speaker != b.speaker for a, b in pairwise(messages))
        assert not any(m.ends_conversation for m in messages[:-1])
        asker, partner = messages[0].speaker, messages[0].partner
        asked[start.day, asker] += 1
        approached[start.day, partner] += 1
    assert max(asked.values(), default=0) <= 1  # each Resident makes one intent a Day
    assert max(approached.values(), default=0) <= APPROACHED_AT_MOST

    wave: set[str] = set()
    for event in events:
        if isinstance(event.payload, ConversationStarted):
            assert not wave & set(event.payload.residents)
            wave |= set(event.payload.residents)
        else:
            wave = set()
