"""Decisions: what the game asks a Resident, and the shape of each answer.

The engine decides which choices are legal. A decision source (a scripted bot,
an Agent or, one day, a human) only picks among them.
"""

from dataclasses import dataclass
from enum import StrEnum

from pydantic import BaseModel, ConfigDict

SKIP = "SKIP"
"""The ballot choice for voting to banish nobody."""


class DecisionKind(StrEnum):
    STATEMENT = "statement"
    BALLOT = "ballot"


@dataclass(frozen=True)
class DecisionRequest:
    kind: DecisionKind
    resident: str
    options: tuple[str, ...] = ()


class Decision(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class Statement(Decision):
    text: str


class Ballot(Decision):
    choice: str
    """A living Resident's name, or SKIP."""
