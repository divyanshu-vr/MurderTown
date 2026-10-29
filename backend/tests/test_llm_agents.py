"""Seam 2: LLM Agents playing whole games against a fake model provider.

Each test scripts how the model answers and asserts on what reaches the event
log and the record of model calls.
"""

from dataclasses import dataclass, replace

import pytest

from mm.agents import ModelCall, llm_agents
from mm.agents.answers import answer_schema
from mm.agents.prompting import prompt_version
from mm.engine import GameConfig, PlayedBy, Role
from mm.engine.decisions import DecisionKind
from mm.engine.events import (
    BallotCast,
    BidPlaced,
    ConversationMessagePosted,
    ConversationStarted,
    DecisionFellBack,
    DenMessagePosted,
    DuskIntentChosen,
    Event,
    GameEnded,
    KillVoteCast,
    LastWordsSpoken,
    RecapNarrated,
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

CONFIG = GameConfig(residents=6, murderers=1, max_days=2, seed=13)
"""Two Days, since Day 1 is only a Night. At this seed its Victim is the Doctor, so the Sheriff
is alive for Day 2's Showdown."""
NIGHTS = GameConfig(residents=8, murderers=2, max_days=2, seed=13)
"""Two Days, so two Murderers talk in the Den and the narrator recaps a Dawn."""


@dataclass
class Played:
    result: GameResult
    calls: list[ModelCall]
    timeline: list[str]
    """'call <decision id>' and 'event <decision id>' in the order they happened."""

    def calls_for(self, kind: DecisionKind) -> list[ModelCall]:
        return [call for call in self.calls if call.kind is kind]


async def play_with(
    model: FakeModel, config: GameConfig = CONFIG, played_by: PlayedBy | None = None
) -> Played:
    calls: list[ModelCall] = []
    timeline: list[str] = []

    async def record(call: ModelCall) -> None:
        calls.append(call)
        timeline.append(f"call {call.decision_id}")

    async def observe(event: Event) -> None:
        if event.decision_id:
            timeline.append(f"event {event.decision_id}")

    agents = llm_agents(model, played_by or PlayedBy(), record, seed=config.seed)
    result = await play_game(config, agents, observers=[observe])
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
    assert call.cost_usd == pytest.approx(0.0000103)  # 40 in, 12 out, 30 read from cache
    assert call.prompt_version == prompt_version()
    assert call.provider == "fake"


async def test_a_bid_is_asked_at_low_effort_whatever_the_residents_own() -> None:
    played = await play_with(FakeModel(), played_by=PlayedBy(effort="high"))

    assert {call.effort for call in played.calls_for(DecisionKind.BID)} == {"low"}
    assert {call.effort for call in played.calls_for(DecisionKind.STATEMENT)} == {"high"}


async def test_an_invalid_answer_is_retried_once_with_the_problem_quoted() -> None:
    def respond(request: ModelRequest) -> ModelReply:
        if answer_kind(request) is DecisionKind.BALLOT and not retried(request):
            return model_answer({"target": "Nobody", "reason": "a hunch"})
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
            return model_answer({"target": "Nobody", "reason": "a hunch"})
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


async def test_an_answer_nested_one_level_down_is_used_without_a_retry() -> None:
    def respond(request: ModelRequest) -> ModelReply:
        if answer_kind(request) is DecisionKind.BID:
            return model_answer({"bid": {"urgency": 3, "reason": "I must speak"}})
        if answer_kind(request) is DecisionKind.RECAP:
            return model_answer({"text": {"text": "Another Day dawns."}})
        return sensible_answer(request)

    played = await play_with(FakeModel(respond), NIGHTS)

    nested = played.calls_for(DecisionKind.BID) + played.calls_for(DecisionKind.RECAP)
    assert nested and all(call.outcome == "ok" for call in nested)
    assert {bid.urgency for bid in payloads(played.result.events, BidPlaced)} == {3}
    recaps = payloads(played.result.events, RecapNarrated)
    assert recaps and {recap.text for recap in recaps} == {"Another Day dawns."}


@pytest.mark.parametrize("kind", list(DecisionKind))
def test_no_answer_is_one_field_holding_an_object_so_a_nested_answer_is_never_mistaken(
    kind: DecisionKind,
) -> None:
    fields = answer_schema(kind)["properties"]

    assert len(fields) > 1 or next(iter(fields.values())).get("type") != "object"


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
                return model_answer({"target": names[0], "reason": "first"})
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
            reply = model_answer({"target": "host@example.com", "reason": "a hunch"})
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


async def test_every_night_decision_and_the_recap_go_through_the_model() -> None:
    played = await play_with(FakeModel(), NIGHTS)

    night_kinds = {
        DecisionKind.DEN_MESSAGE,
        DecisionKind.KILL_VOTE,
        DecisionKind.PROTECT,
        DecisionKind.INVESTIGATE,
        DecisionKind.RECAP,
    }
    assert night_kinds <= {call.kind for call in played.calls}
    assert payloads(played.result.events, DecisionFellBack) == []


async def test_an_unusable_kill_vote_falls_back_to_a_random_legal_victim() -> None:
    def respond(request: ModelRequest) -> ModelReply:
        if answer_kind(request) is DecisionKind.KILL_VOTE:
            return model_answer({"target": "Nobody", "reason": "a hunch"})
        return sensible_answer(request)

    played = await play_with(FakeModel(respond), NIGHTS)

    votes = payloads(played.result.events, KillVoteCast)
    roles = played.result.state.roles
    assert votes
    assert all(roles[vote.target] is not Role.MURDERER for vote in votes)
    fallbacks = payloads(played.result.events, DecisionFellBack)
    assert {fallback.kind for fallback in fallbacks} == {DecisionKind.KILL_VOTE}
    assert len(fallbacks) == len(votes)


async def test_a_den_proposal_of_someone_who_cannot_be_killed_is_dropped_not_retried() -> None:
    def respond(request: ModelRequest) -> ModelReply:
        if answer_kind(request) is DecisionKind.DEN_MESSAGE:
            return model_answer({"text": "Let us take Nobody.", "proposed_victim": "Nobody"})
        return sensible_answer(request)

    played = await play_with(FakeModel(respond), NIGHTS)

    messages = payloads(played.result.events, DenMessagePosted)
    assert messages
    assert {message.proposed_victim for message in messages} == {None}
    assert {call.outcome for call in played.calls_for(DecisionKind.DEN_MESSAGE)} == {"ok"}


async def test_dusk_intents_and_conversation_messages_go_through_the_model() -> None:
    played = await play_with(FakeModel())

    kinds = {call.kind for call in played.calls}
    assert {DecisionKind.DUSK_INTENT, DecisionKind.CONVERSATION_MESSAGE} <= kinds
    assert payloads(played.result.events, ConversationMessagePosted)
    assert payloads(played.result.events, DecisionFellBack) == []


async def test_an_intent_the_model_refuses_falls_back_to_wandering() -> None:
    def respond(request: ModelRequest) -> ModelReply:
        if answer_kind(request) is DecisionKind.DUSK_INTENT:
            return ModelReply(outcome="refusal", data=None, text="", error="the model declined")
        return sensible_answer(request)

    played = await play_with(FakeModel(respond))

    intents = payloads(played.result.events, DuskIntentChosen)
    assert intents
    assert {intent.activity for intent in intents} == {"wander"}
    assert payloads(played.result.events, ConversationStarted) == []


async def test_a_message_the_model_refuses_falls_back_to_ending_the_conversation() -> None:
    def respond(request: ModelRequest) -> ModelReply:
        if answer_kind(request) is DecisionKind.CONVERSATION_MESSAGE:
            return ModelReply(outcome="refusal", data=None, text="", error="the model declined")
        return sensible_answer(request)

    played = await play_with(FakeModel(respond))

    started = payloads(played.result.events, ConversationStarted)
    messages = payloads(played.result.events, ConversationMessagePosted)
    assert started
    assert len(messages) == len(started)
    assert all(m.ends_conversation and m.text == "(says nothing)" for m in messages)
