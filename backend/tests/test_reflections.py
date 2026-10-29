"""Seam 1: when Residents write reflections, who perceives them, and how decisions are linked."""

from collections.abc import Callable

from mm.agents import scripted_bots
from mm.engine import GameConfig, Phase, Role
from mm.engine.events import (
    BallotCast,
    Event,
    PhaseStarted,
    ReflectionWritten,
    ResidentDied,
    StatementMade,
)
from mm.engine.perception import perceived_by
from mm.orchestrator import play_game
from tests.support import everyone_alive_on_day_two, payloads, puppets, seats_by_role, state_before

CONFIG = GameConfig(residents=8, murderers=2, max_days=3, seed=21)


def phase_start(day: int, phase: Phase) -> Callable[[Event], bool]:
    def matches(event: Event) -> bool:
        payload = event.payload
        return isinstance(payload, PhaseStarted) and (payload.day, payload.phase) == (day, phase)

    return matches


async def test_every_living_resident_reflects_after_each_vote() -> None:
    result = await play_game(CONFIG, scripted_bots(seed=21))
    dawns = {p.day for p in payloads(result.events, PhaseStarted) if p.phase is Phase.DAWN}
    days_that_went_on = sorted(day for day in dawns if day + 1 in dawns)

    assert days_that_went_on
    for day in days_that_went_on:
        after_vote = state_before(result.events, phase_start(day + 1, Phase.DAWN))
        writers = [
            event.payload.resident
            for event in result.events
            if isinstance(event.payload, ReflectionWritten)
            and event.day == day
            and event.phase is Phase.VOTE
        ]
        assert sorted(writers) == sorted(after_vote.living)


async def test_nobody_reflects_on_the_opening_night_but_everyone_does_at_the_first_dawn() -> None:
    result = await play_game(CONFIG, scripted_bots(seed=21))
    reflections = [event for event in result.events if isinstance(event.payload, ReflectionWritten)]

    assert not [event for event in reflections if event.day == 1]  # no news yet to reflect on
    first_dawn = sorted(
        event.payload.resident
        for event in reflections
        if isinstance(event.payload, ReflectionWritten)
        and (event.day, event.phase) == (2, Phase.DAWN)
    )
    after_the_news = state_before(result.events, phase_start(2, Phase.DISCUSSION))
    assert first_dawn == sorted(after_the_news.living)


async def test_a_reflection_is_perceived_only_by_its_writer() -> None:
    result = await play_game(CONFIG, scripted_bots(seed=21))
    reflections = payloads(result.events, ReflectionWritten)
    assert reflections

    for resident in result.state.residents:
        perceived = payloads(perceived_by(result.events, resident.name), ReflectionWritten)
        assert {r.resident for r in perceived} <= {resident.name}


async def test_every_event_a_decision_caused_names_that_decision() -> None:
    result = await play_game(CONFIG, scripted_bots(seed=21))

    caused = [
        event
        for event in result.events
        if isinstance(event.payload, StatementMade | BallotCast | ReflectionWritten)
    ]
    ids = [event.decision_id for event in caused]
    assert all(ids)
    assert len(set(ids)) == len(ids)


async def test_nobody_reflects_once_the_game_is_decided() -> None:
    six = GameConfig(residents=6, murderers=1, max_days=3, seed=2)
    roles = seats_by_role(six)
    (murderer,) = roles[Role.MURDERER]
    banish_the_murderer = {seat: murderer for seat in range(6) if seat != murderer}

    result = await play_game(
        six, puppets({2: banish_the_murderer}, **everyone_alive_on_day_two(six))
    )

    death = next(i for i, e in enumerate(result.events) if isinstance(e.payload, ResidentDied))
    assert not [e for e in result.events[death:] if isinstance(e.payload, ReflectionWritten)]
