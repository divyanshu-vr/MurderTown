"""The record of every model call: what was asked, what came back, and what it cost.

A record is written before the event its decision causes, so nothing that
reaches the event log ever lacks the call behind it.
"""

from collections.abc import Awaitable, Callable
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict

from mm.engine.decisions import DecisionKind
from mm.llm import Effort, Outcome

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


CallRecorder = Callable[[ModelCall], Awaitable[None]]
