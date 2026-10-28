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
from mm.agents.lineup import lineup_brains
from mm.engine import GameConfig, Lineup, PlayedBy, Role
from mm.engine.events import BallotCast, Event, KillVoteCast
from mm.llm import ModelProvider
from mm.orchestrator import play_game
from mm.orchestrator.narrator import NARRATOR
from tests.conftest import serving, start_game, wait_until_finished
from tests.support import FakeModel, name_at_seat, seats_by_role

HAIKU = PlayedBy(provider="claude", model="claude-haiku-5-5")
SONNET = PlayedBy(provider="anthropic", model="claude-sonnet-5-5")
OPUS = PlayedBy(provider="openai", model="claude-opus-5-5")


class Named(FakeModel):
    def __init__(self, name: str) -> None:
        super().__init__()
        self.name = name


def providers() -> dict[str, ModelProvider]:
    return {name: Named(name) for name in ("claude", "anthropic", "openai")}


async def ignore(call: ModelCall) -> None: ...


async def played(config: GameConfig) -> list[ModelCall]:
    calls: list[ModelCall] = []

    async def record(call: ModelCall) -> None:
        calls.append(call)

    await play_game(config, lineup_brains(config, providers(), record))
    return calls


async def test_the_murderers_the_town_and_one_seat_can_each_have_their_own_model() -> None:
    base = GameConfig(residents=8, murderers=2, max_days=2, seed=4)
    roles = seats_by_role(base)
    overridden = roles[Role.CIVILIAN][0]
    lineup = Lineup(everyone=HAIKU, murderers=SONNET, seats={overridden: OPUS})
    names = (await play_game(base, scripted_bots(base.seed))).events
    seat_of = {name_at_seat(names, seat): seat for seat in range(base.residents)}

    calls = await played(base.model_copy(update={"lineup": lineup}))

    for call in calls:
        seat = seat_of.get(call.resident)  # the narrator has no seat
        if seat == overridden:
            expected = OPUS
        elif seat in roles[Role.MURDERER]:
            expected = SONNET
        else:
            expected = HAIKU
        assert (call.provider, call.model) == (expected.provider, expected.model), call.resident
    assert {call.provider for call in calls} == {"claude", "anthropic", "openai"}
    assert any(call.resident == NARRATOR.name for call in calls)


async def test_a_lineup_of_scripted_residents_plays_as_scripted_bots_and_calls_no_model() -> None:
    config = GameConfig(residents=6, murderers=1, max_days=1, seed=4)

    by_lineup = await play_game(config, lineup_brains(config, providers(), ignore))

    assert by_lineup.events == (await play_game(config, scripted_bots(config.seed))).events
    assert await played(config) == []


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
        lineup_brains(config, providers(), ignore)


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


def test_a_game_created_with_a_lineup_is_played_by_the_providers_it_names(
    database_url: str,
) -> None:
    lineup = {
        "everyone": HAIKU.model_dump(mode="json"),
        "murderers": SONNET.model_dump(mode="json"),
    }
    config = {"residents": 8, "murderers": 2, "max_days": 2, "seed": 4, "lineup": lineup}
    with serving_on(database_url) as client:
        game_id = start_game(client, config)
        wait_until_finished(client, game_id)
        events = [
            Event.model_validate(e) for e in client.get(f"/games/{game_id}/events").json()["events"]
        ]
        explained = {
            event.payload.type: client.get(f"/games/{game_id}/events/{event.seq}/explain").json()
            for event in events
            if isinstance(event.payload, KillVoteCast | BallotCast)
        }

    assert {a["provider"] for a in explained["kill_vote_cast"]["attempts"]} == {"anthropic"}
    assert {a["provider"] for a in explained["ballot_cast"]["attempts"]} <= {"claude", "anthropic"}
