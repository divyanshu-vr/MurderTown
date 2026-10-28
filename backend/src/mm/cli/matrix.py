"""An evaluation's matrix: which game configurations it plays, and how many games of each.

A matrix is a TOML file. `[base]` is a game configuration (its rules and lineup) that every cell
starts from; `[axes]` lists values for some of its fields, named by their dotted path (such as
`lineup.everyone.effort`), and each combination of those values is a cell. Every cell plays
`games_per_cell` games on the seeds from `first_seed` on, the same seeds in every cell, so cells
differ only in what the axes change.
"""

import copy
import itertools
import tomllib
from pathlib import Path
from typing import Any, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from mm.engine import GameConfig

FIXED = {
    "seed": "each game's seed comes from first_seed",
    "open_floor_seconds": "headless games have no time limit on the Open floor, so that "
    "slower models are not given fewer Statements",
}
"""What a matrix may not set, and why."""


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
        return ", ".join(f"{path}={value}" for path, value in self.values.items()) or "base"

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
    caps: Caps = Caps()

    @model_validator(mode="after")
    def _sets_nothing_fixed(self) -> Self:
        for key in [*self.base, *(path.split(".")[0] for path in self.axes)]:
            if key in FIXED:
                raise ValueError(f"a matrix cannot set {key}: {FIXED[key]}")
        return self

    @classmethod
    def read(cls, path: Path) -> Self:
        return cls.model_validate(tomllib.loads(path.read_text(encoding="utf-8")))

    def cells(self) -> list[Cell]:
        """Every cell, each checked to make a game the rules allow."""
        paths = list(self.axes)
        cells = [
            Cell(index=index, values=dict(zip(paths, combination, strict=True)), base=self.base)
            for index, combination in enumerate(itertools.product(*self.axes.values()))
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
