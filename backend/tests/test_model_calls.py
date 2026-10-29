"""Transport: the Host browses a game's model calls, a page at a time or one whole call."""

import itertools
from typing import Any, NamedTuple

import pytest
from fastapi.testclient import TestClient

from mm.agents import ModelCall
from mm.engine.decisions import decision_number
from tests.conftest import played_to_the_end, spectating

CONFIG = {"residents": 8, "murderers": 2, "max_days": 2, "seed": 4}
WORDS = {"system", "prompt", "raw_text", "answer", "problem"}


def listed(client: TestClient, game_id: str, **params: Any) -> list[dict[str, Any]]:
    response = client.get(f"/games/{game_id}/model-calls", params=params)
    assert response.status_code == 200, response.text
    calls: list[dict[str, Any]] = response.json()["calls"]
    return calls


def asked(call: dict[str, Any]) -> int:
    return decision_number(call["decision_id"])


class Played(NamedTuple):
    """A game played to its end by Agents, and every model call it made."""

    client: TestClient
    game_id: str
    calls: list[ModelCall]


@pytest.fixture
def game(recorded: tuple[TestClient, list[ModelCall]]) -> Played:
    client, calls = recorded
    return Played(client, played_to_the_end(client, CONFIG), calls)


def test_the_host_lists_every_model_call_in_the_order_asked_without_its_words(
    game: Played,
) -> None:
    client, game_id, calls = game

    every = listed(client, game_id, limit=1000)

    keys = {(call["decision_id"], call["attempt"]) for call in every}
    assert keys == {call.key for call in calls}
    assert [asked(call) for call in every] == sorted(asked(call) for call in every)
    assert any(call["attempt"] == 2 for call in every)  # retries are listed too
    assert all(not WORDS & call.keys() for call in every)
    first = every[0]
    assert {"resident", "kind", "outcome", "input_tokens", "cost_usd", "latency_ms"} <= first.keys()


def test_one_residents_calls_are_listed_alone(
    game: Played,
) -> None:
    client, game_id, calls = game
    resident = calls[0].resident

    theirs = listed(client, game_id, resident=resident, limit=1000)

    assert theirs
    assert {call["resident"] for call in theirs} == {resident}
    assert len(theirs) == sum(call.resident == resident for call in calls)


def test_pages_follow_one_another_and_never_split_a_decisions_attempts(
    game: Played,
) -> None:
    client, game_id, _ = game
    every = listed(client, game_id, limit=1000)

    pages: list[list[dict[str, Any]]] = []
    after: str | None = None
    while page := listed(client, game_id, limit=5, **({"after": after} if after else {})):
        pages.append(page)
        after = page[-1]["decision_id"]

    assert [call for page in pages for call in page] == every
    assert all(len({call["decision_id"] for call in page}) <= 5 for page in pages)
    decisions = [{call["decision_id"] for call in page} for page in pages]
    assert all(not (one & other) for one, other in itertools.pairwise(decisions))


def test_the_host_reads_one_call_whole(
    game: Played,
) -> None:
    client, game_id, calls = game
    call = calls[0]

    response = client.get(f"/games/{game_id}/model-calls/{call.decision_id}/{call.attempt}")

    assert response.status_code == 200
    assert response.json() == call.model_dump(mode="json")
    assert client.get(f"/games/{game_id}/model-calls/d999999/1").status_code == 404


def test_only_the_host_may_browse_model_calls(
    game: Played,
) -> None:
    client, game_id, calls = game
    call = calls[0]

    with spectating(client):
        assert client.get(f"/games/{game_id}/model-calls").status_code == 401
        whole = f"/games/{game_id}/model-calls/{call.decision_id}/{call.attempt}"
        assert client.get(whole).status_code == 401


def test_an_unknown_game_or_a_malformed_decision_is_refused(game: Played) -> None:
    client, game_id, _ = game

    assert client.get("/games/no-such-game/model-calls").status_code == 404
    assert client.get("/games/no-such-game/model-calls/d1/1").status_code == 404
    assert client.get(f"/games/{game_id}/model-calls", params={"after": "five"}).status_code == 422
    assert client.get(f"/games/{game_id}/model-calls/five/1").status_code == 422
