"""The model-provider interface: a prompt and an answer schema in, a structured answer out.

Providers only talk to a model. Turning the answer into a game decision, and
deciding what to do when it is unusable, happens once in the agent pipeline,
so every provider behaves the same way to the rest of the game.
"""

from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Literal, Protocol

from mm.engine.decisions import DecisionKind


class Effort(StrEnum):
    """How hard the model thinks before answering: more effort, slower and dearer answers."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    MAX = "max"


Outcome = Literal["ok", "refusal", "timeout", "error"]


@dataclass(frozen=True)
class ModelRequest:
    system: str
    prompt: str
    schema: Mapping[str, Any]
    """The JSON Schema the answer must match."""
    model: str
    effort: Effort
    kind: DecisionKind
    """Which kind of decision the answer is for, so traces and test fakes can tell them apart."""


@dataclass(frozen=True)
class Usage:
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_tokens: int = 0
    cache_write_tokens: int = 0


@dataclass(frozen=True)
class ModelReply:
    outcome: Outcome
    data: dict[str, Any] | None
    """The structured answer, when the model gave one."""
    text: str
    """The raw text of the answer, kept for the record."""
    usage: Usage = field(default_factory=Usage)
    latency_ms: int = 0
    cost_usd: float | None = None
    """What the call would cost at API list prices, as the provider reports it."""
    error: str | None = None


class ModelProvider(Protocol):
    name: str

    async def complete(self, request: ModelRequest) -> ModelReply: ...
