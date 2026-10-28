"""Running an evaluation: a matrix's games played one at a time into a run folder, resumably.

A run folder holds:
- `run.json`: the matrix being played, without its caps, which may change between batches;
- `games/`: each game's file, with its model calls and review beside it as `mm play --out`
  writes them, so the console can replay any of them;
- `games.ndjson`: one line per finished game, tagged with the commit and prompts that played it.
  A line is written only once its game's files are complete, so a run that stopped goes on by
  skipping the games it lists.

A batch stops after its cap of games, or at the first game that aborts: once the subscription's
quota runs out, every game would abort at its first decision. An aborted game is not listed, so
it is played again when the run goes on.
"""

import asyncio
import json
import subprocess
from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict

from mm.agents.lineup import lineup_brains
from mm.agents.prompting import prompt_version
from mm.cli.matrix import Cell, Matrix
from mm.cli.recording import GameRecording, ndjson_line, read_ndjson, write_json
from mm.engine import GameConfig
from mm.engine.events import GameAborted
from mm.llm import ModelProvider
from mm.orchestrator import GameResult, play_game


class Played(BaseModel):
    """One finished game of a run: its cell and seed, its game file (from the run folder), and
    the code and prompts that played it."""

    model_config = ConfigDict(frozen=True)

    cell: int
    seed: int
    file: str
    commit: str
    uncommitted_changes: bool
    prompt_version: str


@dataclass(frozen=True)
class Batch:
    """How many games one batch finished, and why it stopped."""

    played: int
    stopped: Literal["complete", "capped", "aborted"]
    reason: str = ""


class MatrixChangedError(Exception):
    """A run goes on only with the matrix it began with, or its games would not compare."""


class RunFolder:
    def __init__(self, path: Path) -> None:
        self.path = path
        self._matrix = path / "run.json"
        self._ledger = path / "games.ndjson"

    def begin(self, matrix: Matrix) -> None:
        """Keep the matrix a new run plays, or check that a run going on plays the same one."""
        playing = matrix.model_dump(mode="json", exclude={"caps"})
        if not self._matrix.exists():
            write_json(self._matrix, playing)
        elif json.loads(self._matrix.read_text(encoding="utf-8")) != playing:
            raise MatrixChangedError(
                f"{self.path} holds a run of another matrix: give this one a folder of its own"
            )

    def matrix(self) -> Matrix:
        return Matrix.model_validate_json(self._matrix.read_text(encoding="utf-8"))

    def played(self) -> list[Played]:
        return read_ndjson(self._ledger, Played) if self._ledger.exists() else []

    def add(self, game: Played) -> None:
        with self._ledger.open("a", encoding="utf-8", newline="\n") as ledger:
            ledger.write(ndjson_line(game))

    def game_file(self, cell: Cell, seed: int) -> Path:
        return self.path / "games" / f"cell{cell.index:02d}-seed{seed}.ndjson"

    def file_of(self, game: Played) -> Path:
        return self.path / game.file


async def play_batch(
    matrix: Matrix,
    folder: Path,
    providers: Mapping[str, ModelProvider],
    *,
    pause: Callable[[float], Awaitable[None]] = asyncio.sleep,
    on_game: Callable[[Cell, int, GameResult], None] = lambda cell, seed, result: None,
) -> Batch:
    """Play the matrix's games that the run in `folder` has not played yet, until the batch's
    cap, the first aborted game, or the end. `on_game` hears of each game once it is over."""
    run = RunFolder(folder)
    run.begin(matrix)
    done = {(game.cell, game.seed) for game in run.played()}
    commit, uncommitted_changes = code_version()
    played = 0
    for cell, seed in matrix.games():
        if (cell.index, seed) in done:
            continue
        if played == matrix.caps.games_per_batch:
            return Batch(played, "capped")
        if played:
            await pause(matrix.caps.pause_seconds)
        file = run.game_file(cell, seed)
        result = await _play(cell.config(seed), file, providers)
        on_game(cell, seed, result)
        if aborted := [e.payload for e in result.events if isinstance(e.payload, GameAborted)]:
            return Batch(played, "aborted", aborted[0].reason)
        run.add(
            Played(
                cell=cell.index,
                seed=seed,
                file=file.relative_to(folder).as_posix(),
                commit=commit,
                uncommitted_changes=uncommitted_changes,
                prompt_version=prompt_version(),
            )
        )
        played += 1
    return Batch(played, "complete")


async def _play(
    config: GameConfig, file: Path, providers: Mapping[str, ModelProvider]
) -> GameResult:
    recording = GameRecording(file)
    brains = lineup_brains(config, providers, recording.record)
    result = await play_game(config, brains, observers=[recording.events])
    recording.finish(result.events)
    return result


def code_version() -> tuple[str, bool]:
    """The commit the code is checked out at, and whether it has changed since; "unknown" when
    there is no git to ask."""
    try:
        commit = _git("rev-parse", "HEAD")
        return commit, bool(_git("status", "--porcelain"))
    except (OSError, subprocess.CalledProcessError):
        return "unknown", False


def _git(*command: str) -> str:
    return subprocess.run(
        ["git", *command], capture_output=True, text=True, check=True
    ).stdout.strip()
