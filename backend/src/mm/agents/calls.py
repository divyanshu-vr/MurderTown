"""The record of every model call: what was asked, what came back, and what it cost,
and how that record reads as a Langfuse generation.

A record is written before the event its decision causes, so nothing that
reaches the event log ever lacks the call behind it.
"""

import json
from collections.abc import Awaitable, Callable
from typing import Any, Literal

from opentelemetry.trace import Span
from pydantic import BaseModel, ConfigDict

from mm.engine.decisions import DecisionKind
from mm.llm import Effort, Outcome
from mm.observability import tracing

CallOutcome = Outcome | Literal["invalid"]
"""What came of one attempt: the provider's outcome, or an answer the game could not use."""


class ModelCall(BaseModel):
    model_config = ConfigDict(frozen=True)

    decision_id: str
    resident: str
    kind: DecisionKind
    attempt: int
    provider: str
    model: str
    effort: Effort
    prompt_version: str
    system: str
    prompt: str
    outcome: CallOutcome
    problem: str | None
    """Why the answer could not be used, when it could not."""
    raw_text: str
    answer: dict[str, Any] | None
    input_tokens: int
    output_tokens: int
    cache_read_tokens: int
    cache_write_tokens: int
    cost_usd: float | None
    latency_ms: int
    trace_id: str | None
    """The trace of the decision this attempt belongs to, when tracing is on."""


def label_generation(span: Span, call: ModelCall) -> None:
    """Label a model attempt's span as a Langfuse generation, from its record. The trace's
    own labels (who decided, when) reach this span as baggage from the runner."""
    usage = {
        "input": call.input_tokens,
        "output": call.output_tokens,
        "cache_read_input_tokens": call.cache_read_tokens,
        "cache_creation_input_tokens": call.cache_write_tokens,
    }
    span.set_attributes(
        {
            tracing.OBSERVATION_TYPE: "generation",
            tracing.MODEL: call.model,
            tracing.INPUT: json.dumps({"system": call.system, "prompt": call.prompt}),
            tracing.OUTPUT: call.raw_text,
            tracing.USAGE: json.dumps(usage),
            tracing.METADATA + "attempt": call.attempt,
            tracing.METADATA + "outcome": call.outcome,
        }
    )
    tracing.add_tag(span, call.provider)
    if call.cost_usd is not None:
        span.set_attribute(tracing.COST, json.dumps({"total": call.cost_usd}))
    if call.problem:
        span.set_attributes(
            {
                tracing.LEVEL: "WARNING" if call.outcome == "invalid" else "ERROR",
                tracing.STATUS: call.problem,
            }
        )


CallRecorder = Callable[[ModelCall], Awaitable[None]]
