"""Seam 2: what a game looks like in Langfuse.

A game is a session, each decision is a trace, and each model attempt is a
generation inside it. An in-memory exporter catches the spans of a fake-model game.
"""

import json
from collections.abc import Iterator
from dataclasses import dataclass

import pytest
from opentelemetry.sdk.trace import ReadableSpan
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from opentelemetry.trace import NoOpTracerProvider

from mm.agents import AgentSettings, ModelCall, llm_agents
from mm.engine import GameConfig
from mm.engine.decisions import DecisionKind
from mm.llm import ModelReply, ModelRequest
from mm.observability import tracing
from mm.orchestrator import GameResult, play_game
from tests.support import FakeModel, answer_kind, model_answer, sensible_answer

CONFIG = GameConfig(residents=6, murderers=1, max_days=1, seed=13)


@pytest.fixture
def exported() -> Iterator[InMemorySpanExporter]:
    exporter = InMemorySpanExporter()
    tracing.use(tracing.tracer_provider([exporter], batch=False))
    yield exporter
    tracing.use(NoOpTracerProvider())


@dataclass
class Traced:
    result: GameResult
    calls: list[ModelCall]
    decisions: list[ReadableSpan]
    generations: list[ReadableSpan]


async def traced_game(exporter: InMemorySpanExporter, model: FakeModel) -> Traced:
    calls: list[ModelCall] = []

    async def record(call: ModelCall) -> None:
        calls.append(call)

    agents = llm_agents(model, AgentSettings(), record, CONFIG.seed)
    result = await play_game(CONFIG, agents, game_id="game-one")
    spans = list(exporter.get_finished_spans())
    decisions = [span for span in spans if span.name.startswith("decision.")]
    generations = [s for s in spans if attribute(s, tracing.OBSERVATION_TYPE) == "generation"]
    return Traced(result, calls, decisions, generations)


def attribute(span: ReadableSpan, name: str) -> object:
    return (span.attributes or {}).get(name)


def trace_of(span: ReadableSpan) -> str:
    """The span's trace id, written as a model-call record keeps it."""
    return format(span.context.trace_id, "032x")


async def test_each_decision_is_its_own_trace_within_the_games_session(
    exported: InMemorySpanExporter,
) -> None:
    traced = await traced_game(exported, FakeModel())

    every_span = [*traced.decisions, *traced.generations]
    assert {attribute(span, tracing.SESSION) for span in every_span} == {"game-one"}
    assert all(span.parent is None for span in traced.decisions)
    assert len({span.context.trace_id for span in traced.decisions}) == len(traced.decisions)
    decided = {event.decision_id for event in traced.result.events if event.decision_id}
    assert len(traced.decisions) == len(decided)


async def test_each_model_attempt_is_a_generation_under_its_decision(
    exported: InMemorySpanExporter,
) -> None:
    traced = await traced_game(exported, FakeModel())

    decision_spans = {span.context.span_id for span in traced.decisions}
    assert len(traced.generations) == len(traced.calls)
    assert all(g.parent and g.parent.span_id in decision_spans for g in traced.generations)
    trace_ids = {trace_of(g) for g in traced.generations}
    assert {call.trace_id for call in traced.calls} == trace_ids


async def test_a_generation_carries_the_model_its_words_usage_cost_and_metadata(
    exported: InMemorySpanExporter,
) -> None:
    traced = await traced_game(exported, FakeModel())
    call = traced.calls[0]
    (generation,) = [g for g in traced.generations if trace_of(g) == call.trace_id]
    (decision,) = [d for d in traced.decisions if trace_of(d) == call.trace_id]

    assert attribute(generation, tracing.MODEL) == "claude-haiku-5-5"
    assert json.loads(str(attribute(generation, tracing.INPUT))) == {
        "system": call.system,
        "prompt": call.prompt,
    }
    assert attribute(generation, tracing.OUTPUT) == call.raw_text
    assert json.loads(str(attribute(generation, tracing.USAGE))) == {
        "input": 40,
        "output": 12,
        "cache_read_input_tokens": 30,
        "cache_creation_input_tokens": 0,
    }
    assert json.loads(str(attribute(generation, tracing.COST))) == {"total": 0.0002}
    assert attribute(generation, tracing.USER) == call.resident
    assert call.kind is DecisionKind.STATEMENT  # Day 1 opens with Discussion, not reflections
    assert attribute(generation, tracing.TAGS) == ("discussion", "statement", "fake")
    assert attribute(generation, tracing.METADATA + "attempt") == 1
    assert attribute(generation, tracing.METADATA + "outcome") == "ok"
    assert attribute(decision, tracing.TRACE_NAME) == call.kind
    assert attribute(decision, tracing.USER) == call.resident
    assert attribute(decision, tracing.METADATA + "role") in {"murderer", "doctor", "detective",
                                                           "sheriff", "civilian"}  # fmt: skip


async def test_a_retried_decision_shows_both_attempts_the_first_flagged(
    exported: InMemorySpanExporter,
) -> None:
    def ballot_first_names_a_stranger(request: ModelRequest) -> ModelReply:
        retried = "could not be used" in request.prompt
        if answer_kind(request) is DecisionKind.BALLOT and not retried:
            return model_answer({"target": "Nobody", "reason": "a hunch"})
        return sensible_answer(request)

    traced = await traced_game(exported, FakeModel(ballot_first_names_a_stranger))

    ballot = next(call for call in traced.calls if call.kind is DecisionKind.BALLOT)
    attempts = [g for g in traced.generations if trace_of(g) == ballot.trace_id]
    assert [attribute(g, tracing.METADATA + "attempt") for g in attempts] == [1, 2]
    assert attribute(attempts[0], tracing.LEVEL) == "WARNING"
    assert "is not one of the options" in str(attribute(attempts[0], tracing.STATUS))
    assert attribute(attempts[1], tracing.LEVEL) is None
