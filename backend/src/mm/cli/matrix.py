"""An evaluation's matrix: which game configurations it plays, and how many games of each.

A matrix is a TOML file. `[base]` is a game configuration (its rules and lineup) that every cell
starts from; `[axes]` lists values for some of its fields, named by their dotted path (such as
`lineup.everyone.effort`), and each combination of those values is a cell. Every cell plays
`games_per_cell` games on the seeds from `first_seed` on, the same seeds in every cell, so cells
differ only in what the axes change.

An arena is a matrix with `[[contenders]]`: who may play a side. Each Contender plays the
Murderers against each (itself too) as the Town, which adds two axes to the matrix, and since one
seed deals the same seats the same roles, each Contender plays every role as often as any other.
"""

import copy
import itertools
import tomllib
from pathlib import Path
from typing import Any, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from mm.engine import GameConfig, PlayedBy

FIXED = {
    "seed": "each game's seed comes from first_seed",
    "open_floor_seconds": "headless games have no time limit on the Open floor, so that "
    "slower models are not given fewer Statements",
}
"""What a matrix may not set, and why."""

CONTENDER_AXES = {"lineup.murderers": "Murderers", "lineup.town": "Town"}
"""The two axes an arena's Contenders fill, and what a cell's name calls each."""

TAKEN_IN_AN_ARENA = ("lineup.murderers", "lineup.town", "lineup.seats")
"""Who plays a side, or a seat, which in an arena only its Contenders decide."""


def name_of(played_by: PlayedBy) -> str:
    """What the report calls whoever plays: their model, effort and provider."""
    return f"{played_by.model} ({played_by.effort} effort, {played_by.provider})"


class Caps(BaseModel):
    """How much one batch plays before stopping, to stay within the subscription's quota.
    Running the evaluation again goes on where the last batch stopped."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    games_per_batch: int = Field(default=5, ge=1)
    pause_seconds: float = Field(default=0, ge=0)
    """How long to wait between games."""


class Cell(BaseModel):
    """One combination of the axes' values: the configuration its games are played with."""

    model_config = ConfigDict(frozen=True)

    index: int
    values: dict[str, Any]
    """The value of each axis, by its dotted path."""
    base: dict[str, Any]

    @property
    def name(self) -> str:
        return ", ".join(map(_named, self.values.items())) or "base"

    @property
    def conditions(self) -> str:
        """What the cell's name says apart from its Contenders: the same in each of their
        pairings, so with a seed it names the games that mirror each other."""
        return ", ".join(
            _named(item) for item in self.values.items() if item[0] not in CONTENDER_AXES
        )

    def config(self, seed: int) -> GameConfig:
        data = copy.deepcopy(self.base)
        for path, value in self.values.items():
            *parents, field = path.split(".")
            node = data
            for parent in parents:
                node = node.setdefault(parent, {})
            node[field] = value
        return GameConfig.model_validate({**data, "seed": seed, "open_floor_seconds": None})


class Matrix(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str
    games_per_cell: int = Field(ge=1)
    first_seed: int = 1
    base: dict[str, Any] = {}
    axes: dict[str, list[Any]] = {}
    contenders: list[PlayedBy] = []
    caps: Caps = Caps()

    @model_validator(mode="after")
    def _sets_nothing_fixed(self) -> Self:
        for key in [*self.base, *(path.split(".")[0] for path in self.axes)]:
            if key in FIXED:
                raise ValueError(f"a matrix cannot set {key}: {FIXED[key]}")
        return self

    @model_validator(mode="after")
    def _is_a_fair_arena(self) -> Self:
        if not self.contenders:
            return self
        if len(self.contenders) < 2:
            raise ValueError("an arena needs at least two Contenders")
        if len(set(self.contenders)) < len(self.contenders):
            raise ValueError("an arena names the same Contender twice")
        lineup = self.base.get("lineup", {})
        taken = [path for path in TAKEN_IN_AN_ARENA if path.split(".")[1] in lineup]
        taken += [
            path for path in self.axes if path == "lineup" or path.startswith(TAKEN_IN_AN_ARENA)
        ]
        if taken:
            raise ValueError(f"an arena's sides are its Contenders': it cannot set {taken[0]}")
        return self

    @classmethod
    def read(cls, path: Path) -> Self:
        return cls.model_validate(tomllib.loads(path.read_text(encoding="utf-8")))

    def cells(self) -> list[Cell]:
        """Every cell, each checked to make a game the rules allow."""
        axes = dict(self.axes)
        if self.contenders:
            played = [contender.model_dump(mode="json") for contender in self.contenders]
            axes |= dict.fromkeys(CONTENDER_AXES, played)
        paths = list(axes)
        cells = [
            Cell(index=index, values=dict(zip(paths, combination, strict=True)), base=self.base)
            for index, combination in enumerate(itertools.product(*axes.values()))
        ]
        for cell in cells:
            cell.config(self.first_seed)
        return cells

    def games(self) -> list[tuple[Cell, int]]:
        """Every game to play, by cell and seed: each seed in every cell before the next seed,
        so a run stopped early has played every cell about as often."""
        cells = self.cells()
        seeds = range(self.first_seed, self.first_seed + self.games_per_cell)
        return [(cell, seed) for seed in seeds for cell in cells]


def _named(item: tuple[str, Any]) -> str:
    path, value = item
    if path in CONTENDER_AXES:
        return f"{CONTENDER_AXES[path]}: {name_of(PlayedBy.model_validate(value))}"
    return f"{path}={value}"
