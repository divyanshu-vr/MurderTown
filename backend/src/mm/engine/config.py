"""Game configuration: everything the Host chooses before a game starts.

A game is fully determined by its configuration (including the seed) and the
decisions its Residents make. That is what makes every game replayable.
"""

from enum import StrEnum
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from mm.engine.roles import Role, Side

SETUP = ConfigDict(frozen=True, extra="forbid", json_schema_serialization_defaults_required=True)
"""Shared by everything the Host sets up: immutable, strict, and every field always sent."""


class Effort(StrEnum):
    """How hard a Resident's Agent thinks before answering: more effort, slower and dearer."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    MAX = "max"


class PlayedBy(BaseModel):
    """Who plays a Resident: an Agent on a provider's model, or (`"scripted"`) a scripted bot.
    The default is an Agent on Claude Haiku, on the Host's subscription unless an API key is set."""

    model_config = SETUP

    provider: str = "claude"
    model: str = "claude-haiku-5-5"
    effort: Effort = Effort.LOW


SCRIPTED = PlayedBy(provider="scripted")


class Lineup(BaseModel):
    """Who plays each Resident. A seat's own choice wins, then its side's, then everyone's;
    the narrator follows everyone's."""

    model_config = SETUP

    everyone: PlayedBy = SCRIPTED
    murderers: PlayedBy | None = None
    town: PlayedBy | None = None
    seats: dict[int, PlayedBy] = {}

    def played_by(self, seat: int, side: Side) -> PlayedBy:
        by_side = self.murderers if side is Side.MURDERERS else self.town
        return self.seats.get(seat) or by_side or self.everyone


class GameConfig(BaseModel):
    model_config = SETUP

    residents: int = Field(default=12, ge=6, le=15)
    murderers: int = Field(default=2, ge=1, le=3)
    doctor: bool = True
    detective: bool = True
    sheriff: bool = True
    max_days: int = Field(default=10, ge=1, le=20)
    """If the Murderers survive this many Days, they win. Capped to bound a game's cost."""
    open_floor_statements: int = Field(default=8, ge=0, le=20)
    """The most Statements the Open floor allows after the Opening round."""
    open_floor_seconds: int | None = Field(default=300, ge=10, le=3600)
    """A wall-clock limit on the Open floor, for watched games; None turns it off."""
    sheriff_shoots_at: Literal["showdown", "night"] = "showdown"
    """When the Sheriff may fire: in the Showdown each Day, or at Night instead."""
    detective_accuracy: float = Field(default=0.8, ge=0.5, le=1.0)
    """How often the Detective's finding is right. A Detective who is never wrong is too strong."""
    dawn_names_the_saved: bool = True
    """Whether Dawn says who the Doctor saved, or only that someone was saved."""
    seed: int = 0
    lineup: Lineup = Lineup()
    """Who plays each Resident: scripted bots unless the Host chooses Agents."""

    @model_validator(mode="after")
    def _the_lineup_names_only_seats_the_game_has(self) -> Self:
        if strangers := sorted(seat for seat in self.lineup.seats if seat >= self.residents):
            raise ValueError(
                f"the lineup names seat {strangers[0]}, but seats run 0 to {self.residents - 1}"
            )
        return self

    @model_validator(mode="after")
    def _murderers_are_at_most_a_quarter_of_the_town(self) -> Self:
        if self.murderers > self.residents // 4:
            raise ValueError(
                f"{self.murderers} Murderers is more than a quarter of {self.residents} Residents"
            )
        return self

    def role_deck(self) -> list[Role]:
        """One role per Resident, before shuffling: Murderers, enabled specials, then Civilians."""
        specials = [
            role
            for role, enabled in (
                (Role.DOCTOR, self.doctor),
                (Role.DETECTIVE, self.detective),
                (Role.SHERIFF, self.sheriff),
            )
            if enabled
        ]
        deck = [Role.MURDERER] * self.murderers + specials
        return deck + [Role.CIVILIAN] * (self.residents - len(deck))
