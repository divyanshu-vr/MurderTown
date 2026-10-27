"""Seam 2: LLM Agents playing whole games against a fake model provider.

Each test scripts how the model answers and asserts on what reaches the event
log and the record of model calls.
"""

from dataclasses import dataclass

from mm.agents import AgentSettings, ModelCall, llm_agents
from mm.agents.prompting import prompt_version
from mm.engine import GameConfig
from mm.engine.decisions import DecisionKind
from mm.engine.events import BallotCast, DecisionFellBack, Event, GameEnded, StatementMade
from mm.llm import ModelReply, ModelRequest
from mm.orchestrator import GameResult, play_game
from tests.support import FakeModel, answer_kind, model_answer, payloads, sensible_answer

CONFIG = GameConfig(residents=6, murderers=1, max_days=1, seed=13)


@dataclass
class Played:
    result: GameResult
    calls: list[ModelCall]
    timeline: list[str]
    """'call <decision id>' and 'event <decision id>' in the order they happened."""

    def calls_for(self, kind: DecisionKind) -> list[ModelCall]:
        return [call for call in self.calls if call.kind is kind]


async def play_with(model: FakeModel) -> Played:
    calls: list[ModelCall] = []
    timeline: list[str] = []

    async def record(call: ModelCall) -> None:
        calls.append(call)
        timeline.append(f"call {call.decision_id}")

    async def observe(event: Event) -> None:
        if event.decision_id:
            timeline.append(f"event {event.decision_id}")

    agents = llm_agents(model, AgentSettings(), record, seed=CONFIG.seed)
    result = await play_game(CONFIG, agents, observers=[observe])
    return Played(result, calls, timeline)


def retried(request: ModelRequest) -> bool:
    return "Your previous answer could not be used" in request.prompt


async def test_agents_play_a_whole_game_through_the_model_without_fallbacks() -> None:
    played = await play_with(FakeModel())

    assert payloads(played.result.events, GameEnded)
    assert payloads(played.result.events, DecisionFellBack) == []
    assert {(call.outcome, call.attempt) for call in played.calls} == {("ok", 1)}


async def test_every_model_call_is_recorded_before_the_event_its_decision_caused() -> None:
    played = await play_with(FakeModel())

    for call in played.calls:
        assert played.timeline.index(f"call {call.decision_id}") < played.timeline.index(
            f"event {call.decision_id}"
        )


async def test_each_call_records_its_prompt_usage_cost_and_prompt_version() -> None:
    played = await play_with(FakeModel())

    call = played.calls[0]
    assert call.system and call.prompt
    assert (call.input_tokens, call.output_tokens, call.cache_read_tokens) == (40, 12, 30)
    assert call.cost_usd == 0.0002
    assert call.prompt_version == prompt_version()
    assert call.provider == "fake"


async def test_an_invalid_answer_is_retried_once_with_the_problem_quoted() -> None:
    def respond(request: ModelRequest) -> ModelReply:
        if answer_kind(request) is DecisionKind.BALLOT and not retried(request):
            return model_answer({"choice": "Nobody"})
        return sensible_answer(request)

    played = await play_with(FakeModel(respond))

    ballots = played.calls_for(DecisionKind.BALLOT)
    assert [call.outcome for call in ballots[:2]] == ["invalid", "ok"]
    assert ballots[0].decision_id == ballots[1].decision_id
    assert "'Nobody' is not one of the options" in ballots[1].prompt
    assert payloads(played.result.events, DecisionFellBack) == []


async def test_two_invalid_answers_fall_back_to_a_safe_default_and_say_why() -> None:
    def respond(request: ModelRequest) -> ModelReply:
        if answer_kind(request) is DecisionKind.BALLOT:
            return model_answer({"choice": "Nobody"})
        return sensible_answer(request)

    played = await play_with(FakeModel(respond))

    ballots = payloads(played.result.events, BallotCast)
    fallbacks = payloads(played.result.events, DecisionFellBack)
    assert {ballot.target for ballot in ballots} == {None}
    assert {(f.kind, f.resident) for f in fallbacks} == {
        (DecisionKind.BALLOT, ballot.voter) for ballot in ballots
    }
    assert all("'Nobody' is not one of the options" in f.reason for f in fallbacks)
    assert len(played.calls_for(DecisionKind.BALLOT)) == 2 * len(ballots)


async def test_a_refusal_falls_back_without_a_second_try() -> None:
    def respond(request: ModelRequest) -> ModelReply:
        if answer_kind(request) is DecisionKind.STATEMENT:
            return ModelReply(outcome="refusal", data=None, text="", error="the model declined")
        return sensible_answer(request)

    played = await play_with(FakeModel(respond))

    statements = payloads(played.result.events, StatementMade)
    assert {s.text for s in statements} == {"(stays silent)"}
    assert {c.outcome for c in played.calls_for(DecisionKind.STATEMENT)} == {"refusal"}
    assert len(played.calls_for(DecisionKind.STATEMENT)) == len(statements)
    assert {f.reason for f in payloads(played.result.events, DecisionFellBack)} == {
        "the model declined"
    }


async def test_a_timeout_falls_back_without_a_second_try() -> None:
    def respond(request: ModelRequest) -> ModelReply:
        if answer_kind(request) is DecisionKind.STATEMENT:
            return ModelReply(outcome="timeout", data=None, text="", error="no answer in 90s")
        return sensible_answer(request)

    played = await play_with(FakeModel(respond))

    assert {c.outcome for c in played.calls_for(DecisionKind.STATEMENT)} == {"timeout"}
    assert len(played.calls_for(DecisionKind.STATEMENT)) == len(
        payloads(played.result.events, StatementMade)
    )


async def test_details_from_outside_the_game_never_reach_the_event_log() -> None:
    leaky = r"Write to host@example.com, or open C:\Users\host\secrets.txt tonight."

    def respond(request: ModelRequest) -> ModelReply:
        if answer_kind(request) is DecisionKind.STATEMENT:
            return model_answer({"text": leaky})
        return sensible_answer(request)

    played = await play_with(FakeModel(respond))

    text = payloads(played.result.events, StatementMade)[0].text
    assert "host@example.com" not in text
    assert "secrets.txt" not in text
    assert text.count("[hidden]") == 2
