"""Seam 1: the Vote. Sealed ballots, SKIP, ties and banishment."""

from collections.abc import Sequence

import pytest

from mm.agents import Brain
from mm.engine import GameConfig, Resident
from mm.engine.decisions import Answer, DecisionKind, DecisionRequest, Target
from mm.engine.events import (
    BallotCast,
    Event,
    LastWordsSpoken,
    ResidentDied,
    RoleAssigned,
    VoteResolved,
)
from mm.engine.state import GameState
from mm.orchestrator import IllegalDecisionError, play_game
from tests.support import Puppet, name_at_seat, payloads, puppets

SIX_RESIDENTS = GameConfig(residents=6, murderers=1, max_days=1, seed=1)


@pytest.mark.parametrize(
    ("ballots", "banished_seat"),
    [
        pytest.param({0: 5, 1: 5, 2: 5, 3: None, 4: None, 5: 0}, 5, id="plurality beats SKIP"),
        pytest.param({0: 5, 1: 5, 2: 5}, None, id="plurality only equals SKIP"),
        pytest.param({0: 5, 1: 5, 2: 5, 3: 0, 4: 0, 5: 0}, None, id="two Residents tie"),
        pytest.param({}, None, id="everyone skips"),
    ],
)
async def test_the_vote_banishes_the_plurality_only_when_it_beats_skip(
    ballots: dict[int, int | None], banished_seat: int | None
) -> None:
    result = await play_game(SIX_RESIDENTS, puppets({1: ballots}))

    (outcome,) = payloads(result.events, VoteResolved)

    expected = None if banished_seat is None else name_at_seat(result.events, banished_seat)
    assert outcome.banished == expected


async def test_a_banished_resident_dies_and_their_role_is_revealed() -> None:
    result = await play_game(SIX_RESIDENTS, puppets({1: {0: 4, 1: 4, 2: 4, 3: 4}}))
    banished = name_at_seat(result.events, 4)
    (assignment,) = [a for a in payloads(result.events, RoleAssigned) if a.resident == banished]

    (death,) = payloads(result.events, ResidentDied)

    assert (death.resident, death.cause, death.role) == (banished, "banished", assignment.role)


async def test_every_ballot_is_cast_without_seeing_another_ballot_from_the_same_day() -> None:
    ballots_seen_today: list[int] = []

    class Peeking(Puppet):
        async def decide(self, request: DecisionRequest, view: Sequence[Event]) -> Answer:
            if request.kind is DecisionKind.BALLOT:
                today = GameState.fold(view).day
                ballots_seen_today.append(
                    sum(isinstance(e.payload, BallotCast) and e.day == today for e in view)
                )
            return await super().decide(request, view)

    await play_game(SIX_RESIDENTS.model_copy(update={"max_days": 2}), lambda _: Peeking({}))

    assert len(ballots_seen_today) > 6  # both Days' Votes were watched
    assert set(ballots_seen_today) == {0}


async def test_a_ballot_for_someone_who_is_not_an_option_is_rejected() -> None:
    class Cheater(Puppet):
        async def decide(self, request: DecisionRequest, view: Sequence[Event]) -> Answer:
            if request.kind is DecisionKind.BALLOT:
                return Answer(Target(target=request.resident, reason="me"))
            return await super().decide(request, view)

    def make(resident: Resident) -> Brain:
        return Cheater({})

    with pytest.raises(IllegalDecisionError):
        await play_game(SIX_RESIDENTS, make)


async def test_skips_are_counted_apart_from_the_ballots_against_residents() -> None:
    result = await play_game(SIX_RESIDENTS, puppets({1: {0: 5, 1: 5, 2: 3}}))

    (outcome,) = payloads(result.events, VoteResolved)

    assert outcome.tally == {name_at_seat(result.events, 5): 2, name_at_seat(result.events, 3): 1}
    assert outcome.skips == 3


async def test_a_banished_resident_says_last_words_before_their_role_is_revealed() -> None:
    result = await play_game(SIX_RESIDENTS, puppets({1: {0: 4, 1: 4, 2: 4, 3: 4}}))
    banished = name_at_seat(result.events, 4)

    kinds = [type(e.payload).__name__ for e in result.events]
    spoken = kinds.index("LastWordsSpoken")
    assert kinds[spoken + 1] == "ResidentDied"
    (words,) = payloads(result.events, LastWordsSpoken)
    assert words.resident == banished
    assert words.text
