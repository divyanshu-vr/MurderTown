"""When the model fails, the game stops: a timeout or an error aborts it with the reason.

Seam 1 drives it with decision sources that fail like a model that never answered;
seam 2 with a fake model, and with the Claude provider over a stubbed SDK; the
transport tests watch an aborted game the way a Spectator's browser does.
"""

import asyncio
from collections.abc import AsyncIterator, Callable, Mapping, Sequence
from itertools import count
from typing import Any

import pytest
from claude_agent_sdk import ResultError, ResultMessage, SystemMessage
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from mm.agents import AgentSettings, Brain, BrainFactory, CallRecorder, ModelCall, llm_agents
from mm.agents.brain import ModelFailureError
from mm.engine import GameConfig
from mm.engine.decisions import Answer, DecisionKind, DecisionRequest
from mm.engine.events import (
    BallotCast,
    ConversationMessagePosted,
    ConversationStarted,
    DecisionFellBack,
    Event,
    GameAborted,
    KillVoteCast,
    PhaseStarted,
    ResidentProtected,
    VictimChosen,
)
from mm.engine.phases import Phase
from mm.engine.state import GameState
from mm.llm import Effort, ModelReply, ModelRequest
from mm.llm import claude_agent_sdk as sdk
from mm.orchestrator import play_game
from tests.conftest import serving, start_game, wait_until_finished
from tests.support import (
    FakeModel,
    answer_kind,
    may_perceive,
    model_answer,
    name_at_seat,
    payloads,
    played_by,
    puppets,
    sensible_answer,
    wrapped,
)

CONFIG = GameConfig(residents=6, murderers=1, max_days=2, seed=13)

NO_ANSWER = "no answer within 90 seconds"


def no_answer(request: DecisionRequest) -> Exception:
    return ModelFailureError(request, NO_ANSWER)


def crash(request: DecisionRequest) -> Exception:
    return RuntimeError(f"the database is gone while {request.resident} decided")


class Failing:
    """A decision source that fails on chosen requests with `error`, by default as a model
    that never answered would, after letting the event loop run as many times as `waits`
    says for that Resident."""

    def __init__(
        self,
        inner: Brain,
        fails: Callable[[DecisionRequest], bool],
        waits: Mapping[str, int] | None = None,
        error: Callable[[DecisionRequest], Exception] = no_answer,
    ) -> None:
        self.inner, self.fails, self.waits, self.error = inner, fails, waits or {}, error

    async def decide(self, request: DecisionRequest, view: Sequence[Event]) -> Answer:
        if not self.fails(request):
            return await self.inner.decide(request, view)
        for _ in range(self.waits.get(request.resident, 0)):
            await asyncio.sleep(0)
        raise self.error(request)


def failing(
    fails: Callable[[DecisionRequest], bool],
    waits: Mapping[str, int] | None = None,
    error: Callable[[DecisionRequest], Exception] = no_answer,
    **script: Any,
) -> BrainFactory:
    return wrapped(puppets(**script), lambda brain: Failing(brain, fails, waits, error))


def ballots(request: DecisionRequest) -> bool:
    return request.kind is DecisionKind.BALLOT


def aborted(events: Sequence[Event]) -> tuple[Event, GameAborted]:
    """The game's last event, which must say it was aborted."""
    last = events[-1]
    assert isinstance(last.payload, GameAborted), f"the game ended with {last.payload.type}"
    return last, last.payload


async def names_at(*seats: int) -> list[str]:
    """Who sits in these seats: casting is deterministic, so a dry run tells."""
    events = (await play_game(CONFIG, puppets())).events
    return [name_at_seat(events, seat) for seat in seats]


# Seam 1: decision sources that fail


async def test_a_failed_decision_aborts_the_game_naming_who_failed_to_decide_what() -> None:
    (voter,) = await names_at(2)

    result = await play_game(
        CONFIG, failing(lambda r: r.kind is DecisionKind.BALLOT and r.resident == voter)
    )

    event, abort = aborted(result.events)
    assert (abort.resident, abort.kind, abort.reason) == (voter, DecisionKind.BALLOT, NO_ANSWER)
    assert event.decision_id is not None
    assert payloads(result.events, BallotCast) == []
    assert result.state.phase is Phase.ENDED
    assert result.state.winner is None
    assert result.state.aborted


async def test_a_game_that_crashes_still_ends_its_log_with_an_abort_that_names_no_one() -> None:
    logged: list[Event] = []

    async def keep(event: Event) -> None:
        logged.append(event)

    with pytest.raises(RuntimeError, match="database is gone"):
        await play_game(CONFIG, failing(ballots, error=crash), observers=[keep])

    _, abort = aborted(logged)
    assert (abort.resident, abort.kind) == (None, None)
    assert abort.reason == "the game stopped on an internal error"


async def test_when_several_decisions_fail_at_once_the_first_asked_is_the_one_reported() -> None:
    earlier, later = await names_at(1, 3)

    def ballot_of_either(request: DecisionRequest) -> bool:
        return request.kind is DecisionKind.BALLOT and request.resident in (earlier, later)

    logs = []
    for _ in range(2):
        brains = failing(ballot_of_either, waits={earlier: 50, later: 0})  # the later fails first
        result = await play_game(CONFIG, brains)
        assert aborted(result.events)[1].resident == earlier
        logs.append([event.model_dump(mode="json") for event in result.events])
    assert logs[0] == logs[1]


async def test_a_failure_at_night_leaves_that_night_empty_and_is_never_perceived() -> None:
    result = await play_game(CONFIG, failing(lambda r: r.kind is DecisionKind.PROTECT))

    event, abort = aborted(result.events)
    assert abort.kind is DecisionKind.PROTECT
    nightfall = next(
        e.seq
        for e in result.events
        if isinstance(e.payload, PhaseStarted) and e.payload.phase is Phase.NIGHT
    )
    tonight = [e for e in result.events if e.seq > nightfall]
    for kind in (KillVoteCast, ResidentProtected, VictimChosen):
        assert payloads(tonight, kind) == []
    residents = GameState.fold(result.events).residents
    assert not any(may_perceive(event, resident.name) for resident in residents)


async def test_an_abort_mid_conversation_drops_what_that_wave_said() -> None:
    asked = count()

    def the_reply(request: DecisionRequest) -> bool:
        return request.kind is DecisionKind.CONVERSATION_MESSAGE and next(asked) == 1

    result = await play_game(CONFIG, failing(the_reply, talks={1: {0: [1]}}))

    assert payloads(result.events, ConversationStarted)
    assert payloads(result.events, ConversationMessagePosted) == []
    assert aborted(result.events)[1].kind is DecisionKind.CONVERSATION_MESSAGE


# Seam 2: a fake model


async def play_with(
    respond: Callable[[ModelRequest], ModelReply],
) -> tuple[list[Event], list[ModelCall]]:
    return await played_by(FakeModel(respond), CONFIG)


def statements_get(reply: ModelReply) -> Callable[[ModelRequest], ModelReply]:
    def respond(request: ModelRequest) -> ModelReply:
        return reply if answer_kind(request) is DecisionKind.STATEMENT else sensible_answer(request)

    return respond


def raises(error: Exception) -> Callable[[ModelRequest], ModelReply]:
    def respond(request: ModelRequest) -> ModelReply:
        raise error

    return respond


TIMEOUT = ModelReply(outcome="timeout", data=None, text="", error=NO_ANSWER)
ERROR = ModelReply(outcome="error", data=None, text="", error="overloaded")


@pytest.mark.parametrize(
    ("respond", "outcome", "reason"),
    [
        (statements_get(TIMEOUT), "timeout", NO_ANSWER),
        (statements_get(ERROR), "error", "overloaded"),
        (raises(RuntimeError("the connection dropped")), "error", "the connection dropped"),
    ],
    ids=["timeout", "error", "provider raised"],
)
async def test_a_model_that_times_out_or_fails_aborts_the_game_at_once(
    respond: Callable[[ModelRequest], ModelReply], outcome: str, reason: str
) -> None:
    events, calls = await play_with(respond)

    event, abort = aborted(events)
    (failed,) = [call for call in calls if call.decision_id == event.decision_id]
    assert (failed.outcome, failed.attempt, failed.problem) == (outcome, 1, reason)
    assert (abort.resident, abort.kind, abort.reason) == (failed.resident, failed.kind, reason)
    assert payloads(events, DecisionFellBack) == []


async def test_a_retry_that_times_out_aborts_the_game_after_both_attempts_are_recorded() -> None:
    def respond(request: ModelRequest) -> ModelReply:
        if answer_kind(request) is not DecisionKind.BALLOT:
            return sensible_answer(request)
        if "could not be used" in request.prompt:
            return TIMEOUT
        return model_answer({"target": "Nobody", "reason": "a hunch"})

    events, calls = await play_with(respond)

    event, abort = aborted(events)
    ballot = [call for call in calls if call.decision_id == event.decision_id]
    assert [call.outcome for call in ballot] == ["invalid", "timeout"]
    assert abort.kind is DecisionKind.BALLOT


async def test_details_from_outside_the_game_never_reach_an_abort_or_its_record() -> None:
    leaky = r"could not reach host@example.com from C:\Users\host\x.txt"
    events, calls = await play_with(raises(RuntimeError(leaky)))

    event, abort = aborted(events)
    (failed,) = [call for call in calls if call.decision_id == event.decision_id]
    for text in (abort.reason, failed.problem or ""):
        assert "host@example.com" not in text
        assert "C:\\Users" not in text
        assert "[hidden]" in text


# Seam 2: the Claude provider over a stubbed SDK

INIT = SystemMessage(
    subtype="init",
    data={"apiKeySource": "none", "tools": ["StructuredOutput"], "mcp_servers": [], "model": "m"},
)

REQUEST = ModelRequest(
    system="s", prompt="p", schema={}, model="claude-haiku-5-5", effort=Effort.LOW
)


def provider_with(
    monkeypatch: pytest.MonkeyPatch, *messages: object, then: Exception | None = None
) -> sdk.ClaudeAgentSDKProvider:
    """A provider whose sessions yield `messages` and then raise `then`, with no Claude login."""

    async def session(**_: object) -> AsyncIterator[object]:
        for message in messages:
            yield message
        if then:
            raise then

    monkeypatch.setattr(sdk, "claude_cli", lambda: "claude")
    monkeypatch.setattr(sdk, "require_subscription_login", lambda cli: None)
    monkeypatch.setattr(sdk, "query", session)
    return sdk.ClaudeAgentSDKProvider(concurrency=1)


async def test_the_claude_provider_turns_an_sdk_error_into_an_error_reply_keeping_its_tokens(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    result = ResultMessage(
        subtype="success",
        duration_ms=5,
        duration_api_ms=5,
        is_error=True,
        num_turns=1,
        session_id="s",
        usage={"input_tokens": 7, "cache_creation": {"ephemeral_1h_input_tokens": 90}},
        result="API Error: 529 overloaded",
    )
    provider = provider_with(monkeypatch, INIT, result, then=ResultError("exit 1", data={}))

    reply = await provider.complete(REQUEST)

    assert (reply.outcome, reply.error) == ("error", "API Error: 529 overloaded")
    assert (reply.usage.input_tokens, reply.usage.cache_write_1h_tokens) == (7, 90)


async def test_the_claude_provider_reports_an_sdk_error_before_any_result(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    provider = provider_with(monkeypatch, INIT, then=ResultError("Claude Code exited", data={}))

    reply = await provider.complete(REQUEST)

    assert (reply.outcome, reply.error) == ("error", "Claude Code exited")


@pytest.mark.parametrize("subtype", ["error_max_structured_output_retries", "error_max_turns"])
async def test_the_claude_provider_passes_on_an_answer_that_broke_the_rules_to_be_retried(
    monkeypatch: pytest.MonkeyPatch, subtype: str
) -> None:
    result = ResultMessage(
        subtype=subtype,
        duration_ms=5,
        duration_api_ms=5,
        is_error=True,
        num_turns=3,
        session_id="s",
        result="no attempt produced a valid output",
    )
    provider = provider_with(monkeypatch, INIT, result, then=ResultError("exit 1", data={}))

    reply = await provider.complete(REQUEST)

    assert (reply.outcome, reply.data) == ("ok", None)  # the pipeline finds no usable answer


async def test_the_claude_provider_reports_a_failed_isolation_check_as_an_error_reply(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    keyed = SystemMessage(subtype="init", data={**INIT.data, "apiKeySource": "ANTHROPIC_API_KEY"})
    provider = provider_with(monkeypatch, keyed)

    reply = await provider.complete(REQUEST)

    assert reply.outcome == "error"
    assert "isolation check failed" in (reply.error or "")


# Transport: an aborted game, as a Spectator's browser sees it


def timing_out(config: GameConfig, record: CallRecorder) -> BrainFactory:
    return llm_agents(FakeModel(statements_get(TIMEOUT)), AgentSettings(), record, config.seed)


def crashing(config: GameConfig, record: CallRecorder) -> BrainFactory:
    return failing(ballots, error=crash)


def stream_until_aborted(client: TestClient, game_id: str) -> dict[str, Any]:
    """Follow a finished game's stream to its abort, which must also be its end."""
    with client.websocket_connect(f"/ws/games/{game_id}") as socket:
        received = [socket.receive_json()]
        while received[-1]["payload"]["type"] != "game_aborted":
            received.append(socket.receive_json())
        with pytest.raises(WebSocketDisconnect):
            socket.receive_json()
    return received[-1]


def test_an_aborted_games_stream_ends_with_the_abort_which_explains_the_failed_call(
    database_url: str,
) -> None:
    with serving(database_url, timing_out) as client:
        game_id = start_game(client, CONFIG.model_dump(mode="json"))
        wait_until_finished(client, game_id)

        assert client.get(f"/games/{game_id}").json()["status"] == "aborted"
        abort = stream_until_aborted(client, game_id)
        explained = client.get(f"/games/{game_id}/events/{abort['seq']}/explain").json()

    assert abort["visibility"]["scope"] == "spectators"
    assert [attempt["outcome"] for attempt in explained["attempts"]] == ["timeout"]
    assert explained["fallback_reason"] is None


def test_a_crashed_games_stream_ends_too_and_the_game_is_marked_failed(database_url: str) -> None:
    with serving(database_url, crashing) as client:
        game_id = start_game(client, CONFIG.model_dump(mode="json"))
        wait_until_finished(client, game_id)

        assert client.get(f"/games/{game_id}").json()["status"] == "failed"
        abort = stream_until_aborted(client, game_id)

    assert abort["payload"]["reason"] == "the game stopped on an internal error"
