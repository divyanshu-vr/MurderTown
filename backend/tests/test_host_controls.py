"""The Host's controls: pause, step and resume act at checkpoints, before each batch of decisions.

Seam 1 drives them through `play_game`; the transport tests over HTTP, as the Host's browser does.
Pausing changes when a game's events happen, never what they are: a controlled game ends with
the same log as one left alone.
"""

import asyncio
import time
from collections.abc import Sequence
from typing import Any

import pytest
from fastapi.testclient import TestClient

from mm.agents import Brain, BrainFactory, scripted_bots
from mm.engine import GameConfig, Phase
from mm.engine.decisions import Answer, DecisionRequest
from mm.engine.events import BidPlaced, Event, OpenFloorTimedOut, PhaseStarted
from mm.orchestrator import GameControls, GameHaltedError, play_game
from tests.conftest import serving, spectating, start_game, wait_until, wait_until_finished
from tests.support import keen, payloads, puppets, unhurried_bots, wrapped

CONFIG = GameConfig(residents=6, murderers=1, max_days=2, seed=13)


class Counting:
    """Passes decisions through to a scripted bot, noting each one asked."""

    def __init__(self, inner: Brain, asked: list[DecisionRequest]) -> None:
        self.inner, self.asked = inner, asked

    async def decide(self, request: DecisionRequest, view: Sequence[Event]) -> Answer:
        self.asked.append(request)
        return await self.inner.decide(request, view)


def counting(asked: list[DecisionRequest]) -> BrainFactory:
    return wrapped(scripted_bots(CONFIG.seed), lambda brain: Counting(brain, asked))


async def settle() -> None:
    """Let a game run as far as it can before it waits at a checkpoint."""
    for _ in range(500):
        await asyncio.sleep(0)


async def left_alone() -> list[Event]:
    return (await play_game(CONFIG, scripted_bots(CONFIG.seed))).events


# Seam 1


async def test_a_paused_game_asks_nothing_until_resumed_and_then_plays_as_it_would_have() -> None:
    asked: list[DecisionRequest] = []
    controls = GameControls(paused=True)
    game = asyncio.create_task(play_game(CONFIG, counting(asked), controls=controls))

    await settle()
    assert asked == []

    controls.resume()
    assert (await game).events == await left_alone()


async def test_each_step_lets_one_whole_batch_of_decisions_through() -> None:
    asked: list[DecisionRequest] = []
    controls = GameControls(paused=True)
    game = asyncio.create_task(play_game(CONFIG, counting(asked), controls=controls))

    after_each_step = []
    for _ in range(8):
        controls.step()
        await settle()
        after_each_step.append(len(asked))

    # The Opening round asks one Resident at a time; the Open floor's first Turn asks for all
    # six bids at once, then for one Statement.
    assert after_each_step == [1, 2, 3, 4, 5, 6, 12, 13]
    controls.resume()
    assert (await game).events == await left_alone()


async def test_time_held_at_a_checkpoint_does_not_run_down_the_open_floor() -> None:
    now = 0.0
    controls = GameControls(clock=lambda: now)
    config = CONFIG.model_copy(update={"open_floor_seconds": 10})
    paused_once = False

    async def pause_during_the_first_turn(event: Event) -> None:
        nonlocal paused_once
        if isinstance(event.payload, BidPlaced) and not paused_once:
            paused_once = True
            controls.pause()

    observers = [pause_during_the_first_turn]
    game = asyncio.create_task(
        play_game(config, puppets(bids=keen), observers=observers, controls=controls)
    )
    await settle()
    now += 3600  # an hour on the clock while the game waits
    controls.resume()

    assert payloads((await game).events, OpenFloorTimedOut) == []


async def test_a_halt_stops_a_paused_game_where_it_waits() -> None:
    controls = GameControls(paused=True)
    game = asyncio.create_task(play_game(CONFIG, scripted_bots(CONFIG.seed), controls=controls))
    await settle()

    controls.halt()

    with pytest.raises(GameHaltedError):
        await game


async def test_a_resumed_game_catches_up_on_its_stored_log_before_a_pause_holds_it() -> None:
    first_asked: list[DecisionRequest] = []
    stored: list[Event] = []
    halting = GameControls()

    async def store_then_halt_at_the_vote(event: Event) -> None:
        stored.append(event)
        if isinstance(event.payload, PhaseStarted) and event.payload.phase is Phase.VOTE:
            halting.halt()

    with pytest.raises(GameHaltedError):
        observers = [store_then_halt_at_the_vote]
        await play_game(CONFIG, counting(first_asked), observers=observers, controls=halting)

    asked_again: list[DecisionRequest] = []
    controls = GameControls(paused=True)
    game = asyncio.create_task(
        play_game(CONFIG, counting(asked_again), replay=stored, controls=controls)
    )
    await settle()
    assert len(asked_again) == len(first_asked)  # every stored decision made again, nothing new

    controls.resume()
    assert (await game).events == await left_alone()


# Transport


def last_seq(client: TestClient, game_id: str) -> int:
    seq: int = client.get(f"/games/{game_id}").json()["last_seq"]
    return seq


def held_at(client: TestClient, game_id: str) -> int:
    """The last sequence number of a game once it stops growing: the game is held."""
    previous = -1
    while (seq := last_seq(client, game_id)) != previous:
        previous = seq
        time.sleep(0.3)
    return seq


def control(client: TestClient, game_id: str, action: str) -> dict[str, Any]:
    response = client.post(f"/games/{game_id}/{action}")
    assert response.status_code == 200, response.text
    summary: dict[str, Any] = response.json()
    return summary


def test_the_host_pauses_steps_and_resumes_a_game(database_url: str) -> None:
    with serving(database_url, unhurried_bots) as client:
        game_id = start_game(client, CONFIG.model_dump(mode="json"))

        assert client.get(f"/games/{game_id}").json()["controls"] == ["pause"]
        paused = control(client, game_id, "pause")
        assert (paused["status"], paused["controls"]) == ("paused", ["step", "resume"])
        with spectating(client):
            assert client.get(f"/games/{game_id}").json()["controls"] == []
        held = held_at(client, game_id)
        assert control(client, game_id, "step")["status"] == "paused"
        wait_until(lambda: last_seq(client, game_id) > held, "stepped")
        assert control(client, game_id, "resume")["status"] == "running"
        wait_until_finished(client, game_id)
        events = client.get(f"/games/{game_id}/events").json()["events"]
        assert client.get(f"/games/{game_id}").json()["controls"] == []

    assert events == [event.model_dump(mode="json") for event in asyncio.run(left_alone())]


def test_controls_are_the_hosts_alone_and_only_for_a_game_being_played_that_allows_them(
    database_url: str,
) -> None:
    with serving(database_url, unhurried_bots) as client:
        playing = start_game(client, CONFIG.model_dump(mode="json"))
        assert client.post(f"/games/{playing}/step").status_code == 409
        with spectating(client):
            assert client.post(f"/games/{playing}/pause").status_code == 401
        assert client.post("/games/no-such-game/pause").status_code == 404
        control(client, playing, "pause")
        control(client, playing, "resume")
        wait_until_finished(client, playing)

        assert client.post(f"/games/{playing}/pause").status_code == 409


def test_a_paused_game_is_still_paused_when_the_server_starts_again(database_url: str) -> None:
    with serving(database_url, unhurried_bots) as client:
        game_id = start_game(client, CONFIG.model_dump(mode="json"))
        control(client, game_id, "pause")
        held = held_at(client, game_id)

    with serving(database_url, unhurried_bots) as client:
        assert client.get(f"/games/{game_id}").json()["status"] == "paused"
        assert held_at(client, game_id) == held
        control(client, game_id, "resume")
        wait_until_finished(client, game_id)
        events = client.get(f"/games/{game_id}/events").json()["events"]

    assert events == [event.model_dump(mode="json") for event in asyncio.run(left_alone())]
