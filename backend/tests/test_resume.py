"""Resuming a game after the process stopped: the game replays from its seed and ends with
exactly the log it would have had.

Seam 1 crashes a game right after it stored an event, or halts it as a graceful shutdown
does, and resumes it from the events stored so far. Seam 2 does the same with a fake
model, whose recorded calls answer the replay. The transport tests stop a server mid-game
and start another on the same database.
"""

import asyncio
from collections.abc import Callable, Sequence

import pytest
from fastapi.testclient import TestClient

from mm.agents import (
    BrainFactory,
    CallRecorder,
    ModelCall,
    llm_agents,
    scripted_bots,
)
from mm.engine import GameConfig, PlayedBy
from mm.engine.decisions import DecisionKind
from mm.engine.events import (
    BallotCast,
    BidPlaced,
    DecisionFellBack,
    Event,
    GameAborted,
    OpenFloorTimedOut,
    Payload,
    StatementMade,
)
from mm.llm import ModelReply, ModelRequest
from mm.orchestrator import EventObserver, GameControls, GameHaltedError, play_game
from mm.orchestrator.log import ReplayDivergedError
from tests.conftest import following, serving, start_game, wait_until, wait_until_finished
from tests.support import (
    FakeModel,
    agents_on,
    answer_kind,
    everyone_alive_on_day_two,
    keen,
    model_answer,
    puppets,
    sensible_answer,
    ticking,
)

CONFIG = GameConfig(residents=8, murderers=2, max_days=3, seed=4)


class Crashed(BaseException):
    """The process died. Not an `Exception`: nothing in the game gets to clean up after it."""


def never(call: ModelCall) -> bool:
    return False


class Process:
    """What one run of a game stored before it crashed. Once crashed, it stores nothing more."""

    def __init__(self) -> None:
        self.events: list[Event] = []
        self.calls: list[ModelCall] = []
        self.crashed = False

    def alive(self) -> None:
        if self.crashed:
            raise Crashed

    def crash(self) -> None:
        self.crashed = True
        raise Crashed

    def store(self, crashes_at: int | None = None) -> EventObserver:
        async def store(event: Event) -> None:
            self.alive()
            self.events.append(event)
            if event.seq == crashes_at:
                self.crash()

        return store

    def record(self, crashes_after: Callable[[ModelCall], bool] = never) -> CallRecorder:
        async def record(call: ModelCall) -> None:
            self.alive()
            self.calls.append(call)
            if crashes_after(call):
                self.crash()

        return record


def logged(events: Sequence[Event]) -> list[object]:
    return [event.model_dump(mode="json") for event in events]


async def crashed_after(seq: int, brains: BrainFactory, config: GameConfig = CONFIG) -> Process:
    """What a game had stored when it crashed, right after storing event `seq`."""
    process = Process()
    with pytest.raises(Crashed):
        await play_game(config, brains, observers=[process.store(crashes_at=seq)])
    return process


def first_seq_of(kind: str, events: Sequence[Event]) -> int:
    return next(event.seq for event in events if event.payload.type == kind)


SOURCES: dict[str, Callable[[], BrainFactory]] = {
    "scripted bots": lambda: scripted_bots(CONFIG.seed),
    "puppets": lambda: puppets(talks={2: {0: [1]}}, **everyone_alive_on_day_two(CONFIG)),
}

CRASHED_IN = ["statement_made", "ballot_cast", "conversation_message_posted", "kill_vote_cast"]


# Seam 1


@pytest.mark.parametrize("source", SOURCES)
@pytest.mark.parametrize("crashed_in", CRASHED_IN)
async def test_a_game_that_crashed_mid_phase_resumes_to_the_log_it_would_have_had(
    source: str, crashed_in: str
) -> None:
    brains = SOURCES[source]
    uninterrupted = (await play_game(CONFIG, brains())).events
    stored = (await crashed_after(first_seq_of(crashed_in, uninterrupted), brains())).events
    after = Process()

    resumed = await play_game(CONFIG, brains(), observers=[after.store()], replay=stored)

    assert logged(resumed.events) == logged(uninterrupted)
    assert logged([*stored, *after.events]) == logged(uninterrupted)


async def test_a_game_halted_mid_batch_stops_cleanly_and_resumes_to_the_same_log() -> None:
    brains = SOURCES["scripted bots"]
    uninterrupted = (await play_game(CONFIG, brains())).events
    controls = GameControls()
    before = Process()

    async def halt_at_first_ballot(event: Event) -> None:
        if isinstance(event.payload, BallotCast):
            controls.halt()  # the rest of the ballots are already asked: they finish

    with pytest.raises(GameHaltedError):
        observers = [before.store(), halt_at_first_ballot]
        await play_game(CONFIG, brains(), observers=observers, controls=controls)
    resumed = await play_game(CONFIG, brains(), replay=before.events)

    assert not any(isinstance(e.payload, GameAborted) for e in before.events)
    assert logged(resumed.events) == logged(uninterrupted)


async def test_a_replay_that_differs_from_the_stored_log_is_aborted_right_after_it() -> None:
    brains = SOURCES["scripted bots"]
    uninterrupted = (await play_game(CONFIG, brains())).events
    stored = (await crashed_after(first_seq_of("ballot_cast", uninterrupted), brains())).events
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


KEEN = GameConfig(residents=6, murderers=1, max_days=2, seed=4, open_floor_seconds=300)


async def test_an_open_floor_that_ran_out_of_time_does_so_again_when_resumed() -> None:
    timed = await play_game(KEEN, puppets(bids=keen), controls=GameControls(clock=ticking(200)))
    timed_out = first_seq_of("open_floor_timed_out", timed.events)
    process = Process()
    with pytest.raises(Crashed):
        observers = [process.store(timed_out)]
        await play_game(
            KEEN, puppets(bids=keen), observers=observers, controls=GameControls(clock=ticking(200))
        )

    frozen = await play_game(
        KEEN, puppets(bids=keen), controls=GameControls(clock=ticking(0)), replay=process.events
    )

    assert logged(frozen.events) == logged(timed.events)


async def test_an_open_floor_that_had_time_left_keeps_going_when_resumed_on_a_fast_clock() -> None:
    patient = await play_game(KEEN, puppets(bids=keen), controls=GameControls(clock=ticking(0)))
    first_bid = first_seq_of("bid_placed", patient.events)
    stored = (await crashed_after(first_bid, puppets(bids=keen), KEEN)).events

    hasty = await play_game(
        KEEN, puppets(bids=keen), controls=GameControls(clock=ticking(10_000)), replay=stored
    )

    assert isinstance(stored[-1].payload, BidPlaced)  # the stored Turn did not time out, so ...
    assert logged(hasty.events[: len(stored)]) == logged(stored)  # ... the replay did not either
    assert any(isinstance(e.payload, OpenFloorTimedOut) for e in hasty.events[len(stored) :])


# Seam 2: a fake model, whose recorded calls answer the replay

Respond = Callable[[ModelRequest], ModelReply]


def agents(
    model: FakeModel,
    process: Process,
    recorded: Sequence[ModelCall] = (),
    crashes_after: Callable[[ModelCall], bool] = never,
) -> BrainFactory:
    record = process.record(crashes_after)
    return llm_agents(model, PlayedBy(), record, CONFIG.seed, recorded=recorded)


async def crash_and_resume(
    respond: Respond,
    crashes_at: Callable[[list[Event]], int] | None = None,
    crashes_after: Callable[[ModelCall], bool] = never,
) -> tuple[list[Event], Process, Process, Process, FakeModel]:
    """Play a game through, then the same game until it crashes, then resume it, checking the
    resumed game ends with the uninterrupted log. Returns that log, what the full, crashed and
    resumed runs recorded, and the model the resumed run asked."""
    full = Process()
    uninterrupted = (await play_game(CONFIG, agents(FakeModel(respond), full))).events
    before = Process()
    seq = crashes_at(uninterrupted) if crashes_at else None
    with pytest.raises(Crashed):
        brains = agents(FakeModel(respond), before, crashes_after=crashes_after)
        await play_game(CONFIG, brains, observers=[before.store(crashes_at=seq)])
    model, after = FakeModel(respond), Process()
    resumed = await play_game(
        CONFIG, agents(model, after, recorded=before.calls), replay=before.events
    )
    assert logged(resumed.events) == logged(uninterrupted)
    return uninterrupted, full, before, after, model


def keys(calls: Sequence[ModelCall]) -> set[tuple[str, int]]:
    return {call.key for call in calls}


def night_choices_refused(request: ModelRequest) -> ModelReply:
    """Every Night choice is refused, so it falls back to a draw from the Agent's own Random."""
    if answer_kind(request) in (DecisionKind.PROTECT, DecisionKind.INVESTIGATE):
        return ModelReply.failure("the model declined", outcome="refusal")
    return sensible_answer(request)


@pytest.mark.parametrize("crashed_in", CRASHED_IN)
async def test_a_resumed_game_asks_the_model_only_for_the_calls_it_had_not_recorded(
    crashed_in: str,
) -> None:
    _, full, before, after, model = await crash_and_resume(
        night_choices_refused, crashes_at=lambda events: first_seq_of(crashed_in, events)
    )

    assert len(model.requests) == len(full.calls) - len(before.calls)
    assert keys(before.calls) | keys(after.calls) == keys(full.calls)
    assert not keys(before.calls) & keys(after.calls)


async def test_a_retry_cut_short_by_the_crash_is_the_only_call_made_again() -> None:
    def ballots_retried(request: ModelRequest) -> ModelReply:
        retrying = "could not be used" in request.prompt
        if answer_kind(request) is DecisionKind.BALLOT and not retrying:
            return model_answer({"target": "Nobody", "reason": "a hunch"})
        return sensible_answer(request)

    def first_ballot_tried(call: ModelCall) -> bool:
        return call.kind is DecisionKind.BALLOT and call.attempt == 1

    _, _, before, after, _ = await crash_and_resume(
        ballots_retried, crashes_after=first_ballot_tried
    )

    (first_try,) = [call for call in before.calls if first_ballot_tried(call)]
    again = [call for call in after.calls if call.decision_id == first_try.decision_id]
    assert [(call.attempt, call.outcome) for call in again] == [(2, "ok")]


async def test_a_fallback_reason_that_quoted_a_hidden_detail_replays_as_it_was_written() -> None:
    def ballots_name_a_file(request: ModelRequest) -> ModelReply:
        if answer_kind(request) is DecisionKind.BALLOT:
            return model_answer({"target": r"C:\Users\host\notes.txt", "reason": "a hunch"})
        return sensible_answer(request)

    uninterrupted, *_ = await crash_and_resume(
        ballots_name_a_file, crashes_at=lambda events: first_seq_of("ballot_cast", events)
    )

    reasons = [e.payload.reason for e in uninterrupted if isinstance(e.payload, DecisionFellBack)]
    assert reasons
    assert all("[hidden]" in reason and "Users" not in reason for reason in reasons)


async def test_a_game_that_crashed_right_after_its_abort_resumes_to_that_one_abort() -> None:
    def statements_time_out(request: ModelRequest) -> ModelReply:
        if answer_kind(request) is DecisionKind.STATEMENT:
            return ModelReply.failure("no answer within 90 seconds", outcome="timeout")
        return sensible_answer(request)

    uninterrupted, *_ = await crash_and_resume(
        statements_time_out, crashes_at=lambda events: first_seq_of("game_aborted", events)
    )

    assert sum(isinstance(e.payload, GameAborted) for e in uninterrupted) == 1


# Transport: a server stops mid-game, and the next one resumes it

SERVED = {"residents": 8, "murderers": 2, "max_days": 3, "seed": 4, "open_floor_seconds": None}


class UnhurriedModel(FakeModel):
    """A fake model that takes a moment to answer, so a game is still going when the server
    stops. Each call counts as soon as it is made, so one cut off part-way counts too."""

    async def complete(self, request: ModelRequest) -> ModelReply:
        self.requests.append(request)
        await asyncio.sleep(0.005)
        return self.respond(request)


def uninterrupted_game() -> tuple[list[object], int]:
    """The log a served game would have without stopping, and how many model calls it makes."""
    process = Process()
    result = asyncio.run(play_game(GameConfig(**SERVED), agents(FakeModel(), process)))
    return logged(result.events), len(process.calls)


def stopped_mid_game(database_url: str, model: FakeModel) -> tuple[str, list[object]]:
    """A game whose server stopped while it was going, and the events it had stored."""
    with serving(database_url, agents_on(model), shutdown_grace_seconds=5) as client:
        game_id = start_game(client, SERVED)
        wait_until(lambda: client.get(f"/games/{game_id}").json()["last_seq"] >= 80, "got going")
    with serving(database_url, resume_on_boot=False) as client:
        assert client.get(f"/games/{game_id}").json()["status"] == "running"
        return game_id, client.get(f"/games/{game_id}/events").json()["events"]


def streamed(client: TestClient, game_id: str, last: str) -> list[object]:
    with following(client, game_id) as socket:
        received = [socket.receive_json()]
        while received[-1]["payload"]["type"] != last:
            received.append(socket.receive_json())
    return received


def test_a_game_whose_server_stops_mid_game_resumes_when_the_next_one_starts(
    database_url: str,
) -> None:
    expected, calls_needed = uninterrupted_game()
    first, second = UnhurriedModel(), UnhurriedModel()
    game_id, stored = stopped_mid_game(database_url, first)

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
    game_id, stored = stopped_mid_game(database_url, UnhurriedModel())

    def another_town(
        config: GameConfig, record: CallRecorder, recorded: Sequence[ModelCall]
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
