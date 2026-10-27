"""Everything that happens in a game is an event in one append-only log.

Each event type declares who may perceive it (its visibility) right next to its
definition, so the rule for who knows what lives in exactly one place. An
Agent's knowledge is built only from the events it may perceive.
"""

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

from mm.engine.config import GameConfig
from mm.engine.decisions import DecisionKind, Suspicion
from mm.engine.personas import Persona
from mm.engine.phases import Phase
from mm.engine.residents import Resident
from mm.engine.roles import Role, Side

PROTOCOL = ConfigDict(frozen=True, json_schema_serialization_defaults_required=True)
"""Shared by everything sent to the frontend: immutable, and every field always present."""


class Visibility(BaseModel):
    """Who may perceive an event: everyone, a named set of Residents, or Spectators only."""

    model_config = PROTOCOL

    scope: Literal["everyone", "residents", "spectators"]
    residents: tuple[str, ...] = ()

    @classmethod
    def everyone(cls) -> "Visibility":
        return cls(scope="everyone")

    @classmethod
    def only(cls, *residents: str) -> "Visibility":
        return cls(scope="residents", residents=residents)

    @classmethod
    def spectators(cls) -> "Visibility":
        return cls(scope="spectators")

    def allows(self, resident: str) -> bool:
        return self.scope == "everyone" or resident in self.residents


class Payload(BaseModel):
    """Base for every event payload. Each subclass must say who may perceive it."""

    model_config = ConfigDict(**PROTOCOL, extra="forbid")

    def visibility(self) -> Visibility:
        raise NotImplementedError(f"{type(self).__name__} must declare its visibility")


class GameStarted(Payload):
    type: Literal["game_started"] = "game_started"
    config: GameConfig
    residents: tuple[Resident, ...]

    def visibility(self) -> Visibility:
        return Visibility.everyone()


class RoleAssigned(Payload):
    """A Resident learns their role and persona. Murderers also learn who their teammates are."""

    type: Literal["role_assigned"] = "role_assigned"
    resident: str
    role: Role
    persona: Persona
    teammates: tuple[str, ...] = ()

    def visibility(self) -> Visibility:
        return Visibility.only(self.resident)


class PhaseStarted(Payload):
    type: Literal["phase_started"] = "phase_started"
    day: int
    phase: Phase

    def visibility(self) -> Visibility:
        return Visibility.everyone()


class StatementMade(Payload):
    type: Literal["statement_made"] = "statement_made"
    speaker: str
    text: str
    part: Literal["opening_round", "open_floor"]

    def visibility(self) -> Visibility:
        return Visibility.everyone()


class BallotCast(Payload):
    """One Resident's ballot, revealed once every ballot of the Vote has been cast."""

    type: Literal["ballot_cast"] = "ballot_cast"
    voter: str
    target: str | None
    """The Resident voted for, or None for a vote to skip."""

    def visibility(self) -> Visibility:
        return Visibility.everyone()


class VoteResolved(Payload):
    type: Literal["vote_resolved"] = "vote_resolved"
    tally: dict[str, int]
    """Ballots against each Resident who received any."""
    skips: int
    banished: str | None

    def visibility(self) -> Visibility:
        return Visibility.everyone()


class ResidentDied(Payload):
    """A death, announced to everyone with the dead Resident's role."""

    type: Literal["resident_died"] = "resident_died"
    resident: str
    cause: Literal["banished"]
    role: Role

    def visibility(self) -> Visibility:
        return Visibility.everyone()


class ReflectionWritten(Payload):
    """A Resident's private journal entry, rewritten notebook and changed suspicions."""

    type: Literal["reflection_written"] = "reflection_written"
    resident: str
    journal_entry: str
    notebook: str
    suspicions: tuple[Suspicion, ...]

    def visibility(self) -> Visibility:
        return Visibility.only(self.resident)


class DecisionFellBack(Payload):
    """A decision source could not give a usable answer, so a safe default was used instead."""

    type: Literal["decision_fell_back"] = "decision_fell_back"
    resident: str
    kind: DecisionKind
    reason: str

    def visibility(self) -> Visibility:
        return Visibility.spectators()


class GameEnded(Payload):
    type: Literal["game_ended"] = "game_ended"
    winner: Side
    reason: str

    def visibility(self) -> Visibility:
        return Visibility.everyone()


EventPayload = Annotated[
    GameStarted
    | RoleAssigned
    | PhaseStarted
    | StatementMade
    | BallotCast
    | VoteResolved
    | ResidentDied
    | ReflectionWritten
    | DecisionFellBack
    | GameEnded,
    Field(discriminator="type"),
]


class Event(BaseModel):
    """One entry in a game's log: a payload stamped with its place in the game."""

    model_config = PROTOCOL

    seq: int
    day: int
    phase: Phase
    visibility: Visibility
    decision_id: str | None = None
    """The decision that caused this event, if any."""
    payload: EventPayload
