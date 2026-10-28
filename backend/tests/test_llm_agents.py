"""Seam 2: LLM Agents playing whole games against a fake model provider.

Each test scripts how the model answers and asserts on what reaches the event
log and the record of model calls.
"""

from dataclasses import dataclass, replace

from mm.agents import AgentSettings, ModelCall, llm_agents
from mm.agents.prompting import prompt_version
from mm.engine import GameConfig
from mm.engine.decisions import DecisionKind
from mm.engine.events import (
    BallotCast,
    BidPlaced,
    DecisionFellBack,
    Event,
    GameEnded,
    LastWordsSpoken,
    SheriffFired,
    StatementMade,
)
from mm.llm import ModelReply, ModelRequest
from mm.orchestrator import GameResult, play_game
from tests.support import (
    FakeModel,
    answer_kind,
    listed_options,
    model_answer,
    own_role,
    payloads,
    sensible_answer,
    statement_answer,
)

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

    caused = [call for call in played.calls if f"event {call.decision_id}" in played.timeline]
    assert caused
    for call in caused:
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
            return model_answer(statement_answer(leaky, request))
        return sensible_answer(request)

    played = await play_with(FakeModel(respond))

    text = payloads(played.result.events, StatementMade)[0].text
    assert "host@example.com" not in text
    assert "secrets.txt" not in text
    assert text.count("[hidden]") == 2


async def test_a_suspicion_about_someone_outside_the_options_is_retried_with_the_problem() -> None:
    def respond(request: ModelRequest) -> ModelReply:
        if answer_kind(request) is DecisionKind.REFLECTION and not retried(request):
            return model_answer({"journal_entry": "Hmm.", "notebook": "Watch.", "suspicions": [
                {"resident": "Nobody", "suspicion": 90, "note": "a stranger"}]})  # fmt: skip
        return sensible_answer(request)

    played = await play_with(FakeModel(respond))

    reflections = played.calls_for(DecisionKind.REFLECTION)
    assert [call.outcome for call in reflections[:2]] == ["invalid", "ok"]
    assert "not ['Nobody']" in reflections[1].prompt


async def test_a_statement_that_gets_its_own_role_wrong_is_retried_with_the_true_role() -> None:
    def respond(request: ModelRequest) -> ModelReply:
        if answer_kind(request) is DecisionKind.STATEMENT and not retried(request):
            wrong = "civilian" if own_role(request) == "murderer" else "murderer"
            return model_answer(statement_answer("Trust me.", request, my_role=wrong))
        return sensible_answer(request)

    played = await play_with(FakeModel(respond))

    statements = played.calls_for(DecisionKind.STATEMENT)
    assert [call.outcome for call in statements[:2]] == ["invalid", "ok"]
    assert "your true role is" in statements[1].prompt
    assert payloads(played.result.events, DecisionFellBack) == []


async def test_a_shot_at_someone_outside_the_options_falls_back_to_holding_fire() -> None:
    def respond(request: ModelRequest) -> ModelReply:
        if answer_kind(request) is DecisionKind.SHOWDOWN:
            return model_answer({"fire": True, "target": "Nobody", "reason": "a hunch"})
        return sensible_answer(request)

    played = await play_with(FakeModel(respond))

    assert payloads(played.result.events, SheriffFired) == []
    assert [call.outcome for call in played.calls_for(DecisionKind.SHOWDOWN)] == ["invalid"] * 2
    (fallback,) = payloads(played.result.events, DecisionFellBack)
    assert fallback.kind is DecisionKind.SHOWDOWN
    assert "not 'Nobody'" in fallback.reason


async def test_an_unusable_bid_falls_back_to_listening() -> None:
    def respond(request: ModelRequest) -> ModelReply:
        if answer_kind(request) is DecisionKind.BID:
            return model_answer({"urgency": 9, "reason": "me, me, me"})
        return sensible_answer(request)

    played = await play_with(FakeModel(respond))

    bids = payloads(played.result.events, BidPlaced)
    fallbacks = payloads(played.result.events, DecisionFellBack)
    assert bids
    assert {bid.urgency for bid in bids} == {0}
    assert sorted((f.kind, f.resident) for f in fallbacks) == sorted(
        (DecisionKind.BID, bid.resident) for bid in bids
    )


async def test_last_words_the_model_refuses_fall_back_to_saying_nothing() -> None:
    def respond(request: ModelRequest) -> ModelReply:
        match answer_kind(request):
            case DecisionKind.BALLOT:  # everyone votes for the first name, alphabetically
                names = sorted(set(listed_options(request.prompt)) - {"SKIP"})
                return model_answer({"choice": names[0]})
            case DecisionKind.LAST_WORDS:
                return ModelReply(outcome="refusal", data=None, text="", error="the model declined")
            case _:
                return sensible_answer(request)

    played = await play_with(FakeModel(respond))

    (words,) = payloads(played.result.events, LastWordsSpoken)
    (fallback,) = payloads(played.result.events, DecisionFellBack)
    assert words.text == "(says nothing)"
    assert (fallback.kind, fallback.resident) == (DecisionKind.LAST_WORDS, words.resident)


async def test_details_from_outside_the_game_never_reach_a_call_record_or_a_fallback() -> None:
    def respond(request: ModelRequest) -> ModelReply:
        if answer_kind(request) is DecisionKind.BALLOT:
            reply = model_answer({"choice": "host@example.com"})
            return replace(reply, text=reply.text + " see /home/host/notes.txt")
        return sensible_answer(request)

    played = await play_with(FakeModel(respond))

    records = "\n".join(call.model_dump_json() for call in played.calls)
    log = "\n".join(event.model_dump_json() for event in played.result.events)
    assert payloads(played.result.events, DecisionFellBack)
    for text in (records, log):
        assert "host@example.com" not in text
        assert "notes.txt" not in text
        assert "[hidden]" in text
