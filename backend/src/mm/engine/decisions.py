"""Decisions: what the game asks a Resident, and the shape of each answer.

The engine decides which choices are legal. A decision source (a scripted bot,
an Agent or, one day, a human) only picks among them.
"""

from dataclasses import dataclass
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from mm.engine.roles import Role

SKIP = "SKIP"
"""The ballot choice for voting to banish nobody."""

StatementPart = Literal["opening_round", "open_floor"]


class DecisionKind(StrEnum):
    STATEMENT = "statement"
    BID = "bid"
    SHOWDOWN = "showdown"
    BALLOT = "ballot"
    LAST_WORDS = "last_words"
    REFLECTION = "reflection"


@dataclass(frozen=True)
class DecisionRequest:
    kind: DecisionKind
    resident: str
    options: tuple[str, ...] = ()
    part: StatementPart | None = None
    """For a Statement: whether it is made in the Opening round or on the Open floor."""
    id: str = ""
    """Stamped by the game when it asks, so model calls can be linked to the events they caused."""


class Decision(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class Statement(Decision):
    text: str = Field(description="What you say to the town, in your own voice.")
    addressed: list[str] = Field(description="Residents you speak to directly by name.")
    accused: list[str] = Field(description="Residents your words cast suspicion on.")
    defended: list[str] = Field(description="Residents your words stand up for.")
    claimed_role: Role | None = Field(
        description="The role you claim to have, if your words claim one; otherwise null."
    )


class Bid(Decision):
    urgency: int = Field(
        ge=0,
        le=4,
        description=(
            "0 listen, 1 general thoughts, 2 a specific point, 3 urgent, "
            "4 I was addressed and must respond."
        ),
    )
    reason: str = Field(description="Why, in a few words.")


class Showdown(Decision):
    """The Sheriff's choice: hold the single bullet, or fire it at someone now."""

    fire: bool = Field(description="True to fire your only bullet now, false to hold it.")
    target: str | None = Field(description="Whom you fire at, or null when you hold.")
    reason: str = Field(description="Why, in a few words.")


class Ballot(Decision):
    choice: str = Field(description="Exactly one of the options you were given.")


class LastWords(Decision):
    text: str = Field(description="What you say as you leave the town forever.")


class Suspicion(BaseModel):
    model_config = ConfigDict(
        frozen=True, extra="forbid", json_schema_serialization_defaults_required=True
    )

    resident: str = Field(description="Another Resident's name.")
    suspicion: int = Field(
        ge=0, le=100, description="0 = certainly innocent, 100 = certainly a Murderer."
    )
    note: str = Field(description="Why, in a few words.")


class Reflection(Decision):
    """A Resident's private notes to their future self, written twice a Day."""

    journal_entry: str = Field(description="What just happened and what you make of it.")
    notebook: str = Field(
        description="Everything you want to remember for the rest of the game, rewritten in full."
    )
    suspicions: list[Suspicion] = Field(
        description="Residents you have a new or changed opinion about."
    )


@dataclass(frozen=True)
class Answer:
    """A decision source's reply: its decision, and why it fell back to a default if it did."""

    decision: Decision
    fallback_reason: str | None = None
