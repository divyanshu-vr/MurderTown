"""Seam 2 for providers: each model provider over fake HTTP, so no network and no key.

A provider takes one request and gives one reply: the structured answer, its raw text,
the tokens used and how it went. Every failure is a reply, never an exception.
"""

import asyncio
import json
from collections.abc import Callable
from dataclasses import replace
from pathlib import Path
from typing import Any

import httpx2
import pytest

from mm.agents import ModelCall, llm_agents
from mm.agents.answers import answer_schema
from mm.agents.calls import unrecorded
from mm.agents.cassette import Cassette, CassetteMissError
from mm.agents.lineup import lineup_brains
from mm.cli.recording import calls_beside, read_ndjson
from mm.engine import GameConfig, PlayedBy
from mm.engine.decisions import DecisionKind
from mm.engine.events import Event, GameAborted, GameEnded, GameStarted
from mm.llm import Effort, ModelProvider, ModelReply, ModelRequest
from mm.llm import providers as providers_module
from mm.llm.anthropic_api import AnthropicAPIProvider
from mm.llm.openai_compatible import OpenAICompatibleProvider
from mm.llm.providers import Providers
from mm.orchestrator import play_game
from tests.support import FakeModel, answer_kind, model_answer, sensible_answer

REQUEST = ModelRequest(
    system="You are Rosa, the night watchman.",
    memory="Your notebook: watch the forge.",
    task="Cast your ballot.",
    schema={"type": "object", "properties": {"target": {"type": "string"}}},
    model="claude-haiku-5-5",
    effort=Effort.LOW,
)

ANSWER = {"target": "Silas", "reason": "lamps at the forge"}

Handler = Callable[[httpx2.Request], httpx2.Response]


class Sent:
    """The HTTP requests a provider sent, as JSON bodies."""

    def __init__(self) -> None:
        self.bodies: list[dict[str, Any]] = []

    def transport(self, answer: Handler) -> httpx2.AsyncClient:
        def handle(request: httpx2.Request) -> httpx2.Response:
            self.bodies.append(json.loads(request.content))
            return answer(request)

        return httpx2.AsyncClient(transport=httpx2.MockTransport(handle))


def anthropic_message(text: str, stop_reason: str = "end_turn", **usage: int) -> Handler:
    body = {
        "id": "msg_1",
        "type": "message",
        "role": "assistant",
        "model": "claude-haiku-5-5",
        "content": [
            {"type": "thinking", "thinking": "", "signature": "sig"},
            {"type": "text", "text": text},
        ],
        "stop_reason": stop_reason,
        "stop_sequence": None,
        "usage": {
            "input_tokens": usage.get("input", 20),
            "output_tokens": usage.get("output", 7),
            "cache_read_input_tokens": usage.get("read", 300),
            "cache_creation_input_tokens": usage.get("five", 40) + usage.get("hour", 0),
            "cache_creation": {
                "ephemeral_5m_input_tokens": usage.get("five", 40),
                "ephemeral_1h_input_tokens": usage.get("hour", 0),
            },
        },
    }
    return lambda request: httpx2.Response(200, json=body)


def anthropic(sent: Sent, answer: Handler) -> AnthropicAPIProvider:
    client = sent.transport(answer)
    return AnthropicAPIProvider(api_key="test-key", http_client=client, max_retries=0)


async def test_the_anthropic_api_caches_the_briefing_and_the_memory_but_not_the_task() -> None:
    sent = Sent()

    await anthropic(sent, anthropic_message(json.dumps(ANSWER))).complete(REQUEST)

    (body,) = sent.bodies
    assert body["model"] == "claude-haiku-5-5"
    assert body["system"] == [
        {"type": "text", "text": REQUEST.system, "cache_control": {"type": "ephemeral"}}
    ]
    memory, task = body["messages"][0]["content"]
    assert memory == {
        "type": "text",
        "text": REQUEST.memory,
        "cache_control": {"type": "ephemeral"},
    }
    assert task == {"type": "text", "text": REQUEST.task}
    output = body["output_config"]
    assert (output["effort"], output["format"]["type"]) == ("low", "json_schema")
    assert output["format"]["schema"]["properties"] == REQUEST.schema["properties"]


async def test_the_anthropic_api_reads_the_answer_and_every_kind_of_token() -> None:
    reply = await anthropic(
        Sent(), anthropic_message(json.dumps(ANSWER), input=20, output=7, read=300, five=40, hour=9)
    ).complete(REQUEST)

    assert (reply.outcome, reply.data, reply.text) == ("ok", ANSWER, json.dumps(ANSWER))
    usage = reply.usage
    assert (usage.input_tokens, usage.output_tokens, usage.cache_read_tokens) == (20, 7, 300)
    assert (usage.cache_write_5m_tokens, usage.cache_write_1h_tokens) == (40, 9)


async def test_the_anthropic_api_moves_limits_it_cannot_enforce_into_the_schemas_words() -> None:
    sent = Sent()
    bid = replace(REQUEST, schema=answer_schema(DecisionKind.BID))

    await anthropic(sent, anthropic_message(json.dumps({"urgency": 2, "reason": "r"}))).complete(
        bid
    )

    sent_schema = json.dumps(sent.bodies[0]["output_config"]["format"]["schema"])
    assert "minimum" not in json.loads(sent_schema)["properties"]["urgency"]
    assert "maximum: 4" in sent_schema  # kept as words; the pipeline still checks the range


async def test_the_anthropic_api_reports_an_answer_cut_off_at_the_token_limit() -> None:
    reply = await anthropic(Sent(), anthropic_message('{"targ', stop_reason="max_tokens")).complete(
        REQUEST
    )

    assert (reply.outcome, reply.data) == ("error", None)
    assert "16000 tokens" in (reply.error or "")


async def test_the_anthropic_api_reports_a_refusal() -> None:
    reply = await anthropic(Sent(), anthropic_message("", stop_reason="refusal")).complete(REQUEST)

    assert (reply.outcome, reply.data) == ("refusal", None)


def overloaded(request: httpx2.Request) -> httpx2.Response:
    error = {"type": "overloaded_error", "message": "Overloaded"}
    return httpx2.Response(529, json={"type": "error", "error": error})


def too_slow(request: httpx2.Request) -> httpx2.Response:
    raise httpx2.ReadTimeout("no answer", request=request)


@pytest.mark.parametrize(
    ("answer", "outcome"),
    [(overloaded, "error"), (too_slow, "timeout")],
    ids=["overloaded", "slow"],
)
async def test_the_anthropic_api_turns_a_failed_call_into_a_reply(
    answer: Handler, outcome: str
) -> None:
    reply = await anthropic(Sent(), answer).complete(REQUEST)

    assert reply.outcome == outcome
    assert reply.data is None
    assert reply.error


# OpenAI-compatible: OpenAI, OpenRouter, Gemini and xAI


def chat_completion(
    content: str | None, refusal: str | None = None, finish_reason: str = "stop", cached: int = 30
) -> Handler:
    body = {
        "id": "chat_1",
        "object": "chat.completion",
        "created": 1,
        "model": "some-model",
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": content, "refusal": refusal},
                "finish_reason": finish_reason,
            }
        ],
        "usage": {
            "prompt_tokens": 100,
            "completion_tokens": 12,
            "total_tokens": 112,
            "prompt_tokens_details": {"cached_tokens": cached},
        },
    }
    return lambda request: httpx2.Response(200, json=body)


def openai_compatible(
    sent: Sent, answer: Handler, vendor: str = "openai"
) -> OpenAICompatibleProvider:
    return OpenAICompatibleProvider.for_vendor(
        vendor, api_key="test-key", http_client=sent.transport(answer), max_retries=0
    )


def rejecting(option: str, status: int = 400, message: str | None = None) -> Handler:
    """A server that refuses any request carrying `option`, and answers the rest."""

    def answer(request: httpx2.Request) -> httpx2.Response:
        if option in json.loads(request.content):
            error = {"message": message or f"Unsupported parameter: '{option}'", "type": "x"}
            return httpx2.Response(status, json={"error": error})
        return chat_completion(f"Here it is: {json.dumps(ANSWER)}")(request)

    return answer


async def test_an_openai_compatible_provider_asks_in_its_strict_json_schema_at_its_effort() -> None:
    sent = Sent()

    reply = await openai_compatible(sent, chat_completion(json.dumps(ANSWER))).complete(REQUEST)

    (body,) = sent.bodies
    assert body["messages"] == [
        {"role": "system", "content": REQUEST.system},
        {"role": "user", "content": REQUEST.prompt},
    ]
    assert body["response_format"] == {
        "type": "json_schema",
        "json_schema": {"name": "answer", "schema": REQUEST.schema, "strict": True},
    }
    assert body["reasoning_effort"] == "low"
    assert "provider" not in body
    assert (reply.outcome, reply.data) == ("ok", ANSWER)
    usage = reply.usage
    assert (usage.input_tokens, usage.cache_read_tokens, usage.output_tokens) == (70, 30, 12)


async def test_openrouter_only_routes_to_providers_that_honour_every_option() -> None:
    sent = Sent()
    openrouter = openai_compatible(sent, chat_completion(json.dumps(ANSWER)), "openrouter")

    await openrouter.complete(REQUEST)

    assert sent.bodies[0]["provider"] == {"require_parameters": True}


@pytest.mark.parametrize(
    ("answer", "dropped"),
    [
        (rejecting("response_format"), "response_format"),
        (rejecting("reasoning_effort"), "reasoning_effort"),
        (
            rejecting("response_format", 404, "No endpoints found that support it"),
            "response_format",
        ),
    ],
    ids=["format refused", "effort refused", "no endpoint for the format"],
)
async def test_an_option_the_server_refuses_is_dropped_for_that_model_from_then_on(
    answer: Handler, dropped: str
) -> None:
    sent = Sent()
    provider = openai_compatible(sent, answer, "openrouter")

    first = await provider.complete(REQUEST)
    second = await provider.complete(REQUEST)

    refused, accepted, asked_again = sent.bodies
    assert dropped in refused
    assert dropped not in accepted and dropped not in asked_again  # remembered: asked once
    assert first.data == second.data == ANSWER
    if dropped == "response_format":
        assert json.dumps(REQUEST.schema) in accepted["messages"][0]["content"]


@pytest.mark.parametrize(
    "answer",
    [
        chat_completion(None, refusal="I can't help with that."),
        chat_completion("", finish_reason="content_filter"),
    ],
    ids=["refusal", "content filter"],
)
async def test_an_openai_compatible_provider_reports_a_refusal(answer: Handler) -> None:
    reply = await openai_compatible(Sent(), answer).complete(REQUEST)

    assert (reply.outcome, reply.data) == ("refusal", None)


async def test_an_openai_compatible_provider_reads_json_inside_a_fenced_block() -> None:
    fenced = chat_completion(f"```json\n{json.dumps(ANSWER)}\n```")

    reply = await openai_compatible(Sent(), fenced).complete(REQUEST)

    assert reply.data == ANSWER


async def test_an_openai_compatible_provider_turns_a_failed_call_into_a_reply() -> None:
    reply = await openai_compatible(Sent(), overloaded).complete(REQUEST)

    assert (reply.outcome, reply.data) == ("error", None)


async def test_a_call_that_takes_too_long_is_given_up_as_a_timeout() -> None:
    async def never_answers(request: httpx2.Request) -> httpx2.Response:
        await asyncio.sleep(10)
        return httpx2.Response(500)

    client = Sent().transport(never_answers)  # type: ignore[arg-type]
    provider = AnthropicAPIProvider(api_key="k", http_client=client, timeout_s=0.05)

    reply = await provider.complete(REQUEST)

    assert (reply.outcome, reply.error) == ("timeout", "no answer within 0.05 seconds")


# Cassettes: a recorded game's model calls, played back with no model

LIVE_GAME = Path(__file__).parents[2] / "fixtures" / "live-game.ndjson"


def first_ballots_unusable_dusk_refused(request: ModelRequest) -> ModelReply:
    """Sensible answers, but every first ballot names a stranger (so it is retried, quoting the
    problem) and every Dusk intent is refused (so it falls back)."""
    kind = answer_kind(request)
    if kind is DecisionKind.BALLOT and "could not be used" not in request.prompt:
        return model_answer({"target": "Nobody", "reason": "a hunch"})
    if kind is DecisionKind.DUSK_INTENT:
        return ModelReply.failure("the model declined", outcome="refusal")
    return sensible_answer(request)


async def test_a_game_replayed_from_its_recorded_calls_makes_the_same_log_without_the_model() -> (
    None
):
    config = GameConfig(residents=6, murderers=1, max_days=2, seed=3)
    model, calls = FakeModel(first_ballots_unusable_dusk_refused), []

    async def record(call: ModelCall) -> None:
        calls.append(call)

    recorded = await play_game(config, llm_agents(model, PlayedBy(), record, config.seed))
    asked = len(model.requests)

    cassette = Cassette(calls)
    replayed = await play_game(config, llm_agents(cassette, PlayedBy(), unrecorded, config.seed))

    assert {call.outcome for call in calls} >= {"ok", "invalid", "refusal"}
    assert [e.model_dump() for e in replayed.events] == [e.model_dump() for e in recorded.events]
    assert len(model.requests) == asked  # the replay asked no model


async def test_a_request_the_cassette_does_not_hold_fails_loudly_saying_how_to_re_record() -> None:
    with pytest.raises(CassetteMissError, match="re-record"):
        await Cassette([]).complete(REQUEST)


async def test_the_recorded_live_game_replays_exactly_with_no_network() -> None:
    events = read_ndjson(LIVE_GAME, Event)
    calls = read_ndjson(calls_beside(LIVE_GAME), ModelCall)
    started = events[0].payload
    assert isinstance(started, GameStarted)
    assert isinstance(events[-1].payload, GameEnded), "re-record the live game: it did not end"

    replayed = await play_game(
        started.config, lineup_brains(started.config, Cassette.serving(calls), unrecorded)
    )

    last = replayed.events[-1].payload
    assert not isinstance(last, GameAborted), last.reason  # a cassette miss says to re-record
    assert [e.model_dump() for e in replayed.events] == [e.model_dump() for e in events]


# Which provider each name means


def test_claude_means_the_anthropic_api_once_its_key_is_set_and_never_asks_the_subscription(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def no_subscription(**_: object) -> ModelProvider:
        raise AssertionError("the subscription provider was made")

    monkeypatch.setattr(providers_module, "ClaudeAgentSDKProvider", no_subscription)

    keyed = Providers({"anthropic": "sk-test"})

    assert isinstance(keyed["claude"], AnthropicAPIProvider)
    assert isinstance(keyed["anthropic"], AnthropicAPIProvider)


def test_claude_means_the_subscription_when_no_api_key_is_set(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    made: list[ModelProvider] = []

    def subscription(**_: object) -> ModelProvider:
        made.append(FakeModel(name="subscription"))
        return made[-1]

    monkeypatch.setattr(providers_module, "ClaudeAgentSDKProvider", subscription)

    unkeyed = Providers({})

    assert unkeyed["claude"] is unkeyed["claude"] is made[0]  # made once, when first asked for
    assert len(made) == 1


@pytest.mark.parametrize("name", ["anthropic", "openai", "openrouter", "gemini", "xai"])
def test_a_provider_with_no_api_key_is_refused_naming_the_setting(name: str) -> None:
    with pytest.raises(ValueError, match=f"MM_{name.upper()}_API_KEY"):
        Providers({})[name]


def test_an_unknown_provider_is_not_one_of_them() -> None:
    with pytest.raises(KeyError):
        Providers({})["mistral"]
