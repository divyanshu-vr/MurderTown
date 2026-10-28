"""Resuming a game after the process stopped: the game replays from its seed and ends with
exactly the log it would have had.

Seam 1 kills a game right after it stored an event, as a crash would, or halts it as a
graceful shutdown does, and resumes it from the events stored so far. Seam 2 does the
same with a fake model, whose recorded calls answer the replay.
"""

import asyncio
from collections.abc import Callable, Sequence
from itertools import count

import pytest
from fastapi.testclient import TestClient

from mm.agents import (
    AgentSettings,
    BrainFactory,
    CallRecorder,
    ModelCall,
    llm_agents,
    scripted_bots,
)
from mm.api.live_games import BrainsFor
from mm.engine import GameConfig
from mm.engine.decisions import DecisionKind
from mm.engine.events import (
    BallotCast,
    BidPlaced,
    Event,
    GameAborted,
    OpenFloorTimedOut,
    Payload,
    StatementMade,
)
from mm.llm import ModelReply, ModelRequest
from mm.orchestrator import EventObserver, GameHaltedError, play_game
from mm.orchestrator.log import ReplayDivergedError
from tests.conftest import serving, start_game, wait_until, wait_until_finished
from tests.support import FakeModel, answer_kind, model_answer, puppets, sensible_answer

CONFIG = GameConfig(residents=8, murderers=2, max_days=3, seed=4)


class Killed(BaseException):
    """The process died. Not an `Exception`: nothing in the game gets to clean up after it."""


class Process:
    """What one run of the game stored before it died. Once dead, it stores nothing more."""

    def __init__(self) -> None:
        self.events: list[Event] = []
        self.calls: list[ModelCall] = []
        self.dead = False

    def die_if(self, dies: bool) -> None:
        if self.dead or dies:
            self.dead = True
            raise Killed

    def store(self, dies_at: int | None = None) -> EventObserver:
        async def store(event: Event) -> None:
            self.die_if(False)
            self.events.append(event)
            self.die_if(event.seq == dies_at)

        return store

    def record(self, dies_after: Callable[[ModelCall], bool]) -> CallRecorder:
        async def record(call: ModelCall) -> None:
            self.die_if(False)
            self.calls.append(call)
            self.die_if(dies_after(call))

        return record


def logged(events: Sequence[Event]) -> list[object]:
    return [event.model_dump(mode="json") for event in events]


async def killed_after(seq: int, brains: BrainFactory) -> Process:
    """What a game had stored when it was killed, right after storing event `seq`."""
    process = Process()
    with pytest.raises(Killed):
        await play_game(CONFIG, brains, observers=[process.store(dies_at=seq)])
    return process


async def first_seq_of(kind: str, brains: BrainFactory) -> int:
    """Where an event of this type first happens in an uninterrupted game."""
    events = (await play_game(CONFIG, brains)).events
    return next(event.seq for event in events if event.payload.type == kind)


SOURCES: dict[str, Callable[[], BrainFactory]] = {
    "scripted bots": lambda: scripted_bots(CONFIG.seed),
    "puppets": lambda: puppets(talks={1: {0: [1]}}),
}

KILLED_IN = ["statement_made", "ballot_cast", "conversation_message_posted", "kill_vote_cast"]


# Seam 1


@pytest.mark.parametrize("source", SOURCES)
@pytest.mark.parametrize("killed_in", KILLED_IN)
async def test_a_game_killed_mid_phase_resumes_to_the_log_it_would_have_had(
    source: str, killed_in: str
) -> None:
    brains = SOURCES[source]
    uninterrupted = (await play_game(CONFIG, brains())).events
    stored = (await killed_after(await first_seq_of(killed_in, brains()), brains())).events
    after = Process()

    resumed = await play_game(CONFIG, brains(), observers=[after.store()], replay=stored)

    assert logged(resumed.events) == logged(uninterrupted)
    assert logged([*stored, *after.events]) == logged(uninterrupted)


async def test_a_game_halted_mid_batch_stops_cleanly_and_resumes_to_the_same_log() -> None:
    brains = SOURCES["scripted bots"]
    uninterrupted = (await play_game(CONFIG, brains())).events
    halt = asyncio.Event()
    before = Process()

    async def halt_at_first_ballot(event: Event) -> None:
        if isinstance(event.payload, BallotCast):
            halt.set()  # the rest of the ballots are already asked: they finish

    with pytest.raises(GameHaltedError):
        await play_game(
            CONFIG, brains(), observers=[before.store(), halt_at_first_ballot], halt=halt
        )
    resumed = await play_game(CONFIG, brains(), replay=before.events)

    assert not any(isinstance(e.payload, GameAborted) for e in before.events)
    assert logged(resumed.events) == logged(uninterrupted)


async def test_a_replay_that_differs_from_the_stored_log_is_aborted_right_after_it() -> None:
    brains = SOURCES["scripted bots"]
    stored = (await killed_after(await first_seq_of("ballot_cast", brains()), brains())).events
    changed = next(e for e in stored if isinstance(e.payload, StatementMade))
    altered: Payload = changed.payload.model_copy(update={"text": "Not what was said."})
    tampered = [e.model_copy(update={"payload": altered}) if e is changed else e for e in stored]
    after = Process()

    with pytest.raises(ReplayDivergedError) as diverged:
        await play_game(CONFIG, brains(), observers=[after.store()], replay=tampered)

    assert diverged.value.seq == changed.seq
    (abort,) = after.events  # the stored log is left as it was, with only the abort after it
    assert abort.seq == len(tampered) + 1
    assert isinstance(abort.payload, GameAborted)
    assert abort.payload.reason == "resuming the game did not reproduce its log"


def ticking(seconds_per_look: int) -> Callable[[], float]:
    looks = count(start=0, step=seconds_per_look)
    return lambda: next(looks)


KEEN = GameConfig(residents=6, murderers=1, max_days=1, seed=4, open_floor_seconds=300)


def keen(name: str, known: object) -> int:
    return 2


def keen_puppets() -> BrainFactory:
    """Every Resident always wants to speak, so only the time limit ends the Open floor."""
    return puppets(bids=keen)


async def test_an_open_floor_that_ran_out_of_time_does_so_again_when_resumed() -> None:
    brains = keen_puppets
    timed = await play_game(KEEN, brains(), clock=ticking(200))
    timed_out = next(e.seq for e in timed.events if isinstance(e.payload, OpenFloorTimedOut))
    process = Process()
    with pytest.raises(Killed):
        await play_game(KEEN, brains(), observers=[process.store(timed_out)], clock=ticking(200))

    frozen = await play_game(KEEN, brains(), clock=lambda: 0.0, replay=process.events)

    assert logged(frozen.events) == logged(timed.events)


async def test_an_open_floor_that_had_time_left_keeps_going_when_resumed_on_a_fast_clock() -> None:
    brains = keen_puppets
    patient = await play_game(KEEN, brains(), clock=lambda: 0.0)
    first_bid = next(e.seq for e in patient.events if isinstance(e.payload, BidPlaced))
    process = Process()
    with pytest.raises(Killed):
        await play_game(KEEN, brains(), observers=[process.store(first_bid)], clock=lambda: 0.0)

    hasty = await play_game(KEEN, brains(), clock=ticking(10_000), replay=process.events)

    replayed = hasty.events[: len(process.events)]  # the stored Turn did not time out, so ...
    assert logged(replayed) == logged(process.events)  # ... the replay did not either
    assert any(isinstance(e.payload, OpenFloorTimedOut) for e in hasty.events[len(replayed) :])


# Seam 2: a fake model, whose recorded calls answer the replay


def never(call: ModelCall) -> bool:
    return False


def agents(
    model: FakeModel,
    process: Process,
    replay: Sequence[ModelCall] = (),
    dies_after: Callable[[ModelCall], bool] = never,
) -> BrainFactory:
    record = process.record(dies_after)
    return llm_agents(model, AgentSettings(), record, CONFIG.seed, replay=replay)


def keyed(calls: Sequence[ModelCall]) -> set[tuple[str, int]]:
    return {(call.decision_id, call.attempt) for call in calls}


def night_choices_refused(request: ModelRequest) -> ModelReply:
    """Every Night choice is refused, so it falls back to a draw from the Agent's own Random."""
    if answer_kind(request) in (DecisionKind.PROTECT, DecisionKind.INVESTIGATE):
        return ModelReply.failure("the model declined", outcome="refusal")
    return sensible_answer(request)


@pytest.mark.parametrize("killed_in", KILLED_IN)
async def test_a_resumed_game_asks_the_model_only_for_the_calls_it_had_not_recorded(
    killed_in: str,
) -> None:
    full = Process()
    uninterrupted = (await play_game(CONFIG, agents(FakeModel(night_choices_refused), full))).events
    seq = next(e.seq for e in uninterrupted if e.payload.type == killed_in)
    before = Process()
    with pytest.raises(Killed):
        brains = agents(FakeModel(night_choices_refused), before)
        await play_game(CONFIG, brains, observers=[before.store(dies_at=seq)])
    model, after = FakeModel(night_choices_refused), Process()

    resumed = await play_game(
        CONFIG, agents(model, after, replay=before.calls), replay=before.events
    )

    assert logged(resumed.events) == logged(uninterrupted)
    assert len(model.requests) == len(full.calls) - len(before.calls)
    assert keyed(before.calls) | keyed(after.calls) == keyed(full.calls)
    assert not keyed(before.calls) & keyed(after.calls)


async def test_a_retry_cut_short_by_the_crash_is_the_only_call_made_again() -> None:
    def ballots_retried(request: ModelRequest) -> ModelReply:
        retrying = "could not be used" in request.prompt
        if answer_kind(request) is DecisionKind.BALLOT and not retrying:
            return model_answer({"target": "Nobody", "reason": "a hunch"})
        return sensible_answer(request)

    full = Process()
    uninterrupted = (await play_game(CONFIG, agents(FakeModel(ballots_retried), full))).events
    first_try = next(c for c in full.calls if c.kind is DecisionKind.BALLOT)
    before = Process()
    with pytest.raises(Killed):
        brains = agents(
            FakeModel(ballots_retried), before, dies_after=lambda call: call == first_try
        )
        await play_game(CONFIG, brains, observers=[before.store()])
    model, after = FakeModel(ballots_retried), Process()

    resumed = await play_game(
        CONFIG, agents(model, after, replay=before.calls), replay=before.events
    )

    assert logged(resumed.events) == logged(uninterrupted)
    again = [c for c in after.calls if c.decision_id == first_try.decision_id]
    assert [(c.attempt, c.outcome) for c in again] == [(2, "ok")]


# Transport: a server stops mid-game, and the next one resumes it

SERVED = {"residents": 8, "murderers": 2, "max_days": 3, "seed": 4, "open_floor_seconds": None}


class UnhurriedModel(FakeModel):
    """A fake model that takes a moment to answer, so a game is still going when we stop."""

    async def complete(self, request: ModelRequest) -> ModelReply:
        await asyncio.sleep(0.005)
        return await super().complete(request)


def agents_on(model: FakeModel) -> BrainsFor:
    def brains_for(
        config: GameConfig, record: CallRecorder, replay: Sequence[ModelCall]
    ) -> BrainFactory:
        return llm_agents(model, AgentSettings(), record, config.seed, replay=replay)

    return brains_for


def uninterrupted_game() -> tuple[list[object], int]:
    """The log a served game would have without stopping, and how many model calls it makes."""
    process = Process()
    config = GameConfig(**SERVED)
    brains = llm_agents(FakeModel(), AgentSettings(), process.record(never), config.seed)
    result = asyncio.run(play_game(config, brains))
    return logged(result.events), len(process.calls)


def stopped_mid_game(database_url: str, brains_for: BrainsFor) -> tuple[str, list[object]]:
    """A game whose server stopped while it was going, and the events it had stored."""
    with serving(database_url, brains_for, shutdown_grace_seconds=5) as client:
        game_id = start_game(client, SERVED)
        wait_until(lambda: client.get(f"/games/{game_id}").json()["last_seq"] >= 80, "got going")
    with serving(database_url, resume_on_boot=False) as client:
        assert client.get(f"/games/{game_id}").json()["status"] == "running"
        return game_id, client.get(f"/games/{game_id}/events").json()["events"]


def streamed(client: TestClient, game_id: str, last: str) -> list[object]:
    with client.websocket_connect(f"/ws/games/{game_id}?after=0") as socket:
        received = [socket.receive_json()]
        while received[-1]["payload"]["type"] != last:
            received.append(socket.receive_json())
    return received


def test_a_game_whose_server_stops_mid_game_resumes_when_the_next_one_starts(
    database_url: str,
) -> None:
    expected, calls_needed = uninterrupted_game()
    first, second = UnhurriedModel(), UnhurriedModel()
    game_id, stored = stopped_mid_game(database_url, agents_on(first))

    with serving(database_url, agents_on(second)) as client:
        wait_until_finished(client, game_id)
        events = client.get(f"/games/{game_id}/events").json()["events"]
        watched = streamed(client, game_id, last="game_ended")
        status = client.get(f"/games/{game_id}").json()["status"]

    assert 80 <= len(stored) < len(expected)
    assert status == "finished"
    assert events == expected
    assert watched == expected  # a Spectator who reconnects gets every event once
    assert len(first.requests) + len(second.requests) == calls_needed  # none made twice


def test_a_game_that_resumes_differently_is_aborted_right_after_its_stored_log(
    database_url: str,
) -> None:
    game_id, stored = stopped_mid_game(database_url, agents_on(UnhurriedModel()))

    def another_town(
        config: GameConfig, record: CallRecorder, replay: Sequence[ModelCall]
    ) -> BrainFactory:
        return scripted_bots(config.seed + 1)  # not the Agents that played it

    with serving(database_url, another_town) as client:
        wait_until_finished(client, game_id)
        events = client.get(f"/games/{game_id}/events").json()["events"]
        status = client.get(f"/games/{game_id}").json()["status"]

    assert status == "failed"
    assert events[:-1] == stored
    assert events[-1]["seq"] == len(stored) + 1
    assert events[-1]["payload"]["reason"] == "resuming the game did not reproduce its log"
