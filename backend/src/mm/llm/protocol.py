"""The model-provider interface: a prompt and an answer schema in, a structured answer out.

Providers only talk to a model. Turning the answer into a game decision, and
deciding what to do when it is unusable, happens once in the agent pipeline,
so every provider behaves the same way to the rest of the game. Providers report
the tokens a call used; its cost comes from the one price table (`prices.py`).
"""

from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Literal, Protocol


class Effort(StrEnum):
    """How hard the model thinks before answering: more effort, slower and dearer answers."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    MAX = "max"


Outcome = Literal["ok", "refusal", "timeout", "error"]

CALL_TIMEOUT_S = 90.0
"""How long a provider waits for one answer before giving up, unless told otherwise."""


@dataclass(frozen=True)
class ModelRequest:
    system: str
    prompt: str
    schema: Mapping[str, Any]
    """The JSON Schema the answer must match."""
    model: str
    effort: Effort


@dataclass(frozen=True)
class Usage:
    """Tokens one call used. Cache writes are split by how long they last, because a
    write that lasts an hour costs more than one that lasts five minutes."""

    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_tokens: int = 0
    cache_write_5m_tokens: int = 0
    cache_write_1h_tokens: int = 0

    @property
    def cache_write_tokens(self) -> int:
        return self.cache_write_5m_tokens + self.cache_write_1h_tokens


@dataclass(frozen=True)
class ModelReply:
    outcome: Outcome
    data: dict[str, Any] | None
    """The structured answer, when the model gave one."""
    text: str
    """The raw text of the answer, kept for the record."""
    usage: Usage = field(default_factory=Usage)
    latency_ms: int = 0
    error: str | None = None

    @classmethod
    def failure(cls, error: str, outcome: Outcome = "error") -> "ModelReply":
        """A call that brought back no answer at all."""
        return cls(outcome=outcome, data=None, text="", error=error)


class ModelProvider(Protocol):
    """Talks to one kind of model. A failed call is a reply (`ModelReply.failure`), not an
    exception; the pipeline treats a provider that raises anyway as an error too."""

    name: str

    async def complete(self, request: ModelRequest) -> ModelReply: ...
