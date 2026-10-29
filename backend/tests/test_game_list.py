"""Transport: the game list, and what the setup form may offer."""

from typing import Any

import pytest
from fastapi.testclient import TestClient

from tests.conftest import serving, spectating, start_game, wait_until_finished
from tests.support import FakeModel, agents_on

CONFIG = {"residents": 6, "murderers": 1, "max_days": 2, "seed": 4}


def listed(client: TestClient) -> list[dict[str, Any]]:
    response = client.get("/games")
    assert response.status_code == 200, response.text
    games: list[dict[str, Any]] = response.json()["games"]
    return games


def test_the_game_list_shows_each_games_status_day_phase_winner_and_cost_newest_first(
    database_url: str,
) -> None:
    with serving(database_url, agents_on(FakeModel())) as client:
        older, newer = start_game(client, CONFIG), start_game(client, CONFIG)
        for game_id in (older, newer):
            wait_until_finished(client, game_id)
        cost = client.get(f"/games/{newer}/cost").json()["total"]["cost_usd"]
        last = client.get(f"/games/{newer}/events").json()["events"][-1]

        games = listed(client)
        with spectating(client):
            seen_in_public = listed(client)

    assert [game["id"] for game in games] == [newer, older]
    newest = games[0]
    assert newest["status"] == "finished"
    assert (newest["day"], newest["phase"]) == (last["day"], "ended")
    assert newest["winner"] == last["payload"]["winner"]
    assert newest["cost_usd"] == pytest.approx(cost)  # added up in another order
    assert cost > 0
    # how the cost grows could tell who is thinking at Night, so only the Host sees it
    assert [game["cost_usd"] for game in seen_in_public] == [None, None]
    assert "config" not in newest  # its seed would tell every role


def test_the_setup_form_may_offer_every_provider_and_every_priced_model(
    client: TestClient,
) -> None:
    with spectating(client):
        choices = client.get("/setup-choices").json()

    assert {"scripted", "claude", "anthropic", "openai"} <= set(choices["providers"])
    assert "claude-haiku-5-5" in choices["models"]


SONNET_MURDERERS = {
    "residents": 8,
    "murderers": 2,
    "lineup": {
        "everyone": {"provider": "claude", "model": "claude-haiku-5-5"},
        "murderers": {"provider": "claude", "model": "claude-sonnet-5-5"},
    },
}


def test_the_host_sees_what_a_setup_would_cost_before_starting_it(client: TestClient) -> None:
    response = client.post("/estimates", json=SONNET_MURDERERS)

    assert response.status_code == 200, response.text
    estimate = response.json()
    assert set(estimate["by_model"]) == {"claude-haiku-5-5", "claude-sonnet-5-5"}
    assert estimate["usd"] == pytest.approx(sum(estimate["by_model"].values()))
    assert estimate["days"] >= 2


def test_only_the_host_may_ask_and_only_of_a_setup_the_rules_allow(client: TestClient) -> None:
    refused = client.post("/estimates", json={**SONNET_MURDERERS, "murderers": 3})
    unpriced = {"lineup": {"everyone": {"provider": "claude", "model": "no-such-model"}}}
    unknown = client.post("/estimates", json=unpriced)
    with spectating(client):
        spectator = client.post("/estimates", json=SONNET_MURDERERS)

    assert refused.status_code == unknown.status_code == 422
    assert "no-such-model" in unknown.json()["detail"]
    assert spectator.status_code == 401
