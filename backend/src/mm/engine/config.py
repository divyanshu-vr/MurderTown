"""Game configuration: everything the Host chooses before a game starts.

A game is fully determined by its configuration (including the seed) and the
decisions its Residents make. That is what makes every game replayable.
"""

from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from mm.engine.roles import Role


class GameConfig(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    residents: int = Field(default=12, ge=6, le=15)
    murderers: int = Field(default=2, ge=1, le=3)
    doctor: bool = True
    detective: bool = True
    sheriff: bool = True
    max_days: int = Field(default=10, ge=1, le=10)
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
