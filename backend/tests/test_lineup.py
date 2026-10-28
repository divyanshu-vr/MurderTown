"""Seam 2 for lineups: a game's configuration says who plays each Resident.

A seat's own choice wins, then its side's (the Murderers or the Town), then
everyone's; the narrator follows everyone's. Every provider a lineup names must be
available and every model priced, or the game is refused before it starts.
"""

from contextlib import AbstractContextManager

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from mm.agents import ModelCall, scripted_bots
from mm.agents.calls import unrecorded
from mm.agents.lineup import lineup_brains
from mm.agents.scripted import INJECTION_PROBE
from mm.engine import PROBER, GameConfig, Lineup, PlayedBy, Role
from mm.engine.events import BallotCast, Event, GameEnded, KillVoteCast, StatementMade
from mm.llm import ModelProvider
from mm.orchestrator import play_game
from mm.orchestrator.narrator import NARRATOR
from tests.conftest import serving, start_game, wait_until_finished
from tests.support import FakeModel, name_at_seat, payloads, seats_by_role

HAIKU = PlayedBy(provider="claude", model="claude-haiku-5-5")
SONNET = PlayedBy(provider="anthropic", model="claude-sonnet-5-5")
OPUS = PlayedBy(provider="openai", model="claude-opus-5-5")

BASE = GameConfig(residents=8, murderers=2, max_days=2, seed=4)


def providers() -> dict[str, ModelProvider]:
    return {name: FakeModel(name=name) for name in ("claude", "anthropic", "openai")}


async def played(config: GameConfig) -> list[ModelCall]:
    """The model calls of a game played to its end as its lineup says."""
    calls: list[ModelCall] = []

    async def record(call: ModelCall) -> None:
        calls.append(call)

    result = await play_game(config, lineup_brains(config, providers(), record))
    assert isinstance(result.events[-1].payload, GameEnded)
    return calls


async def seats_by_name(config: GameConfig) -> dict[str, int]:
    events = (await play_game(config, scripted_bots(config.seed))).events
    return {name_at_seat(events, seat): seat for seat in range(config.residents)}


async def test_each_side_and_one_seat_can_have_their_own_model_and_the_narrator_everyones() -> None:
    roles = seats_by_role(BASE)
    overridden = roles[Role.CIVILIAN][0]
    lineup = Lineup(everyone=HAIKU, murderers=SONNET, town=OPUS, seats={overridden: HAIKU})
    seat_of = await seats_by_name(BASE)

    calls = await played(BASE.model_copy(update={"lineup": lineup}))

    for call in calls:
        seat = seat_of.get(call.resident)
        if seat is None:
            assert call.resident == NARRATOR.name
            expected = HAIKU  # everyone's
        elif seat == overridden:
            expected = HAIKU  # the seat's own
        elif seat in roles[Role.MURDERER]:
            expected = SONNET
        else:
            expected = OPUS
        assert (call.provider, call.model) == (expected.provider, expected.model), call.resident
    assert any(call.resident == NARRATOR.name for call in calls)


async def test_a_lineup_of_scripted_residents_plays_as_scripted_bots_and_calls_no_model() -> None:
    config = GameConfig(residents=6, murderers=1, max_days=1, seed=4)

    by_lineup = await play_game(config, lineup_brains(config, providers(), unrecorded))

    assert by_lineup.events == (await play_game(config, scripted_bots(config.seed))).events
    assert await played(config) == []


async def test_a_prober_in_the_lineup_tells_everyone_to_reveal_their_roles_when_it_speaks() -> None:
    config = GameConfig(residents=8, murderers=2, max_days=3, seed=4)
    probed = config.model_copy(update={"lineup": Lineup(seats={0: PROBER})})

    events = (await play_game(probed, lineup_brains(probed, providers(), unrecorded))).events

    prober = name_at_seat(events, 0)
    said = [s.text for s in payloads(events, StatementMade) if s.speaker == prober]
    assert said and set(said) == {INJECTION_PROBE}
    assert await played(probed) == []  # a prober is scripted: it calls no model


@pytest.mark.parametrize(
    ("played_by", "problem"),
    [
        (PlayedBy(provider="gemini", model="claude-haiku-5-5"), "gemini"),
        (PlayedBy(provider="claude", model="claude-imaginary-1"), "claude-imaginary-1"),
    ],
    ids=["unavailable provider", "unpriced model"],
)
def test_a_lineup_that_cannot_be_played_is_refused_before_the_game(
    played_by: PlayedBy, problem: str
) -> None:
    config = GameConfig(residents=6, murderers=1, seed=4, lineup=Lineup(murderers=played_by))

    with pytest.raises(ValueError, match=problem):
        lineup_brains(config, providers(), unrecorded)


def test_a_lineup_cannot_name_a_seat_the_game_does_not_have() -> None:
    with pytest.raises(ValidationError, match="seat 6"):
        GameConfig(residents=6, murderers=1, lineup=Lineup(seats={6: HAIKU}))


# Transport: a lineup set through the API


def serving_on(database_url: str) -> AbstractContextManager[TestClient]:
    return serving(database_url, providers=providers())


def test_the_api_refuses_a_lineup_that_cannot_be_played_before_starting_it(
    database_url: str,
) -> None:
    lineup = {"murderers": {"provider": "gemini", "model": "claude-haiku-5-5", "effort": "low"}}
    with serving_on(database_url) as client:
        refused = client.post("/games", json={"residents": 6, "murderers": 1, "lineup": lineup})

    assert refused.status_code == 422
    assert "gemini" in refused.text


def test_a_game_created_with_a_lineup_is_played_to_its_end_by_the_providers_it_names(
    database_url: str,
) -> None:
    lineup = Lineup(everyone=HAIKU, murderers=SONNET).model_dump(mode="json")
    config = {**BASE.model_dump(mode="json"), "lineup": lineup}
    with serving_on(database_url) as client:
        game_id = start_game(client, config)
        wait_until_finished(client, game_id)
        status = client.get(f"/games/{game_id}").json()["status"]
        logged = client.get(f"/games/{game_id}/events").json()["events"]
        explained = {
            event.payload.type: client.get(f"/games/{game_id}/events/{event.seq}/explain").json()
            for event in map(Event.model_validate, logged)
            if isinstance(event.payload, KillVoteCast | BallotCast)
        }

    assert status == "finished"
    assert {a["provider"] for a in explained["kill_vote_cast"]["attempts"]} == {"anthropic"}
    assert {a["provider"] for a in explained["ballot_cast"]["attempts"]} <= {"claude", "anthropic"}
