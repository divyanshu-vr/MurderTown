"""The record of every model call: what was asked, what came back, and what it cost;
how that record reads as a Langfuse generation; and what many calls cost together.

A record is written before the event its decision causes, so nothing that
reaches the event log ever lacks the call behind it.
"""

import json
from collections.abc import Awaitable, Callable, Iterable
from typing import Any, ClassVar, Literal, Self

from opentelemetry.trace import Span
from pydantic import BaseModel, ConfigDict, computed_field

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
    cost_usd: float
    """Equivalent cost: what the call would cost at the Claude API's list prices."""
    latency_ms: int
    trace_id: str | None
    """The trace of the decision this attempt belongs to, when tracing is on."""


class Cost(BaseModel):
    """What some model calls used and cost together: the cost meter's numbers.

    Prompt tokens are every token the model read, whether billed as plain input,
    read from the cache or written to it.
    """

    model_config = ConfigDict(frozen=True, json_schema_serialization_defaults_required=True)

    SUMMED: ClassVar = ("input_tokens", "output_tokens", "cache_read_tokens", "cache_write_tokens",
                        "cost_usd")  # fmt: skip
    """The figures of a call that add up across calls."""

    calls: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_tokens: int = 0
    cache_write_tokens: int = 0
    cost_usd: float = 0.0

    @computed_field  # type: ignore[prop-decorator]
    @property
    def prompt_tokens(self) -> int:
        return self.input_tokens + self.cache_read_tokens + self.cache_write_tokens

    @computed_field  # type: ignore[prop-decorator]
    @property
    def cache_hit_rate(self) -> float | None:
        """The share of prompt tokens read from the cache, or None before any prompt."""
        return self.cache_read_tokens / self.prompt_tokens if self.prompt_tokens else None

    @classmethod
    def of(cls, calls: Iterable[ModelCall]) -> Self:
        total = cls()
        for call in calls:
            total += cls(calls=1, **call.model_dump(include=set(cls.SUMMED)))
        return total

    def __add__(self, other: Self) -> Self:
        counted = ("calls", *self.SUMMED)
        return type(self)(**{name: getattr(self, name) + getattr(other, name) for name in counted})


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
    span.set_attribute(tracing.COST, json.dumps({"total": call.cost_usd}))
    if call.problem:
        span.set_attributes(
            {
                tracing.LEVEL: "WARNING" if call.outcome == "invalid" else "ERROR",
                tracing.STATUS: call.problem,
            }
        )


CallRecorder = Callable[[ModelCall], Awaitable[None]]
