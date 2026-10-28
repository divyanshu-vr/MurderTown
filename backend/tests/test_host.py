"""Transport: the Host token. Only the Host may start games and see a game's full scope;
everyone else is a Spectator with public scope, sent only what the whole town saw."""

import time
from collections.abc import Sequence
from concurrent.futures import ThreadPoolExecutor
from typing import Any

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from mm.agents import BrainFactory, CallRecorder, ModelCall, scripted_bots
from mm.engine import GameConfig
from mm.engine.events import Event, GameConfigured
from tests.conftest import following, played_to_the_end, serving, spectating, start_game
from tests.support import unhurried_bots

CONFIG = {"residents": 8, "murderers": 2, "max_days": 2, "seed": 4}


def public(events: Sequence[dict[str, Any]]) -> list[dict[str, Any]]:
    return [event for event in events if event["visibility"]["scope"] == "everyone"]


def logged(client: TestClient, game_id: str, **params: Any) -> list[dict[str, Any]]:
    response = client.get(f"/games/{game_id}/events", params=params)
    assert response.status_code == 200, response.text
    events: list[dict[str, Any]] = response.json()["events"]
    return events


def test_only_the_host_may_start_a_game(client: TestClient) -> None:
    with spectating(client):
        assert client.post("/games", json=CONFIG).status_code == 401
        wrong = client.post("/games", json=CONFIG, headers={"X-Host-Token": "guess"})
        assert wrong.status_code == 401

    assert client.post("/games", json=CONFIG).status_code == 201


def test_a_game_the_host_gives_no_seed_is_dealt_a_random_one(client: TestClient) -> None:
    unseeded = {key: value for key, value in CONFIG.items() if key != "seed"}

    seeds = []
    for _ in range(2):
        configured = Event.model_validate(logged(client, played_to_the_end(client, unseeded))[0])
        assert isinstance(configured.payload, GameConfigured)
        seeds.append(configured.payload.config.seed)

    assert seeds[0] != seeds[1]
    assert 0 not in seeds  # the default would be easy to guess, and the seed tells every role


def test_a_spectator_is_sent_only_what_the_whole_town_saw(client: TestClient) -> None:
    game_id = played_to_the_end(client, CONFIG)

    everything = logged(client, game_id)
    with spectating(client):
        seen = logged(client, game_id)
        page = logged(client, game_id, after=3, limit=5)

    assert {event["visibility"]["scope"] for event in everything} > {"everyone"}
    assert seen == public(everything)
    assert "game_configured" not in {event["payload"]["type"] for event in seen}  # nor the seed
    assert page == [event for event in seen if event["seq"] > 3][:5]  # pages stay full
    assert seen[-1]["payload"]["type"] == "game_ended"


def test_a_wrong_host_token_is_refused_not_given_less(client: TestClient) -> None:
    game_id = played_to_the_end(client, CONFIG)

    with spectating(client):
        response = client.get(f"/games/{game_id}/events", headers={"X-Host-Token": "guess"})

    assert response.status_code == 401


@pytest.mark.parametrize("path", ["residents/{name}/mind", "events/{seq}/explain", "cost"])
def test_only_the_host_may_look_inside_a_game(client: TestClient, path: str) -> None:
    game_id = played_to_the_end(client, CONFIG)
    ballot = next(e for e in logged(client, game_id) if e["payload"]["type"] == "ballot_cast")
    url = f"/games/{game_id}/" + path.format(name=ballot["payload"]["voter"], seq=ballot["seq"])

    assert client.get(url).status_code == 200
    with spectating(client):
        assert client.get(url).status_code == 401


def test_a_spectators_socket_streams_only_what_the_whole_town_saw_to_the_end(
    client: TestClient,
) -> None:
    game_id = played_to_the_end(client, CONFIG)
    seen = public(logged(client, game_id))

    with spectating(client), client.websocket_connect(f"/ws/games/{game_id}") as socket:
        received = [socket.receive_json() for _ in seen]
        with pytest.raises(WebSocketDisconnect):
            socket.receive_json()  # the game is over

    assert received == seen


def test_a_spectators_socket_follows_a_game_being_played_with_only_what_the_town_sees(
    database_url: str,
) -> None:
    with serving(database_url, unhurried_bots) as client:
        game_id = start_game(client, CONFIG)
        with spectating(client), client.websocket_connect(f"/ws/games/{game_id}") as socket:
            received = [socket.receive_json()]
            while received[-1]["payload"]["type"] != "game_ended":
                received.append(socket.receive_json())
        everything = logged(client, game_id)

    assert received == public(everything)


def test_the_hosts_socket_streams_everything_once_it_sends_the_token(client: TestClient) -> None:
    game_id = played_to_the_end(client, CONFIG)
    everything = logged(client, game_id)

    with following(client, game_id) as socket:
        received = [socket.receive_json() for _ in everything]

    assert received == everything


def test_a_socket_asking_for_full_scope_with_a_wrong_token_is_closed(client: TestClient) -> None:
    game_id = played_to_the_end(client, CONFIG)

    with client.websocket_connect(f"/ws/games/{game_id}?scope=full") as socket:
        socket.send_text("guess")
        with pytest.raises(WebSocketDisconnect) as closed:
            socket.receive_json()

    assert closed.value.code == 4401


def test_starting_games_is_rate_limited(database_url: str) -> None:
    with serving(database_url, new_games_per_hour=2) as client:
        for _ in range(2):
            start_game(client, CONFIG)

        refused = client.post("/games", json=CONFIG)

    assert refused.status_code == 429
    assert int(refused.headers["Retry-After"]) > 0


def slow_to_check(
    config: GameConfig, record: CallRecorder, recorded: Sequence[ModelCall]
) -> BrainFactory:
    """Scripted bots, after a moment spent checking the lineup, so requests sent at once overlap."""
    time.sleep(0.2)
    return scripted_bots(config.seed)


def test_requests_sent_at_once_start_no_more_games_than_the_limit(database_url: str) -> None:
    with serving(database_url, slow_to_check, new_games_per_hour=2) as client:

        def start() -> int:
            return client.post("/games", json=CONFIG).status_code

        with ThreadPoolExecutor(max_workers=4) as pool:
            statuses = [pool.submit(start) for _ in range(4)]

    assert sorted(status.result() for status in statuses) == [201, 201, 429, 429]


def test_a_refused_game_does_not_count_against_the_limit(database_url: str) -> None:
    with serving(database_url, new_games_per_hour=1) as client:
        unplayable = {**CONFIG, "lineup": {"everyone": {"provider": "gemini"}}}
        assert client.post("/games", json=unplayable).status_code == 422

        assert client.post("/games", json=CONFIG).status_code == 201


@pytest.mark.parametrize(
    ("origin", "allowed"), [("http://localhost:5173", True), ("https://elsewhere.example", False)]
)
def test_only_the_frontends_origin_may_call_from_a_browser(
    client: TestClient, origin: str, allowed: bool
) -> None:
    preflight = client.options(
        "/games",
        headers={
            "Origin": origin,
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "x-host-token",
        },
    )

    assert (preflight.headers.get("access-control-allow-origin") == origin) is allowed


def test_the_server_will_not_start_without_a_host_token(database_url: str) -> None:
    with pytest.raises(ValueError, match="MM_HOST_TOKEN"), serving(database_url, host_token=None):
        pass
