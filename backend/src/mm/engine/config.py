"""Game configuration: everything the Host chooses before a game starts.

A game is fully determined by its configuration (including the seed) and the
decisions its Residents make. That is what makes every game replayable.
"""

from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from mm.engine.roles import Role


class GameConfig(BaseModel):
    model_config = ConfigDict(
        frozen=True, extra="forbid", json_schema_serialization_defaults_required=True
    )

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
    seed: int = 0

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
