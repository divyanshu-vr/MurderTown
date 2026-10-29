"""The evaluation harness: a matrix of game configurations played headlessly into a run folder,
resumably, and reported with confidence intervals.

Matrices here are small and scripted, so their games take a fraction of a second.
"""

from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError
from typer.testing import CliRunner

from mm.agents.prompting import prompt_version
from mm.cli import app
from mm.cli.evaluation import (
    Batch,
    MatrixChangedError,
    RunBusyError,
    RunFolder,
    code_version,
    play_batch,
)
from mm.cli.matrix import Matrix
from mm.cli.report import write_report
from mm.cli.tables import percentile
from mm.engine import PROBER, Effort
from mm.llm import ModelReply
from mm.review.measures import Measures
from tests.support import FakeModel

SCRIPTED_ONLY: dict[str, FakeModel] = {}
"""No provider: a scripted matrix calls no model."""

MATRICES = Path(__file__).parents[2] / "configs" / "evaluations"


def tiny(**changes: Any) -> Matrix:
    """Two cells of two games each, as small and short as games go."""
    matrix: dict[str, Any] = {
        "name": "tiny",
        "games_per_cell": 2,
        "base": {"residents": 6, "murderers": 1, "max_days": 2},
        "axes": {"detective_accuracy": [0.6, 1.0]},
    }
    return Matrix.model_validate(matrix | changes)


def on_claude(**changes: Any) -> Matrix:
    """The tiny matrix, two Days long (the opening Night, then one full Day), with Agents on
    Claude in every seat."""
    lineup = {"everyone": {"provider": "claude"}}
    return tiny(base={"residents": 6, "murderers": 1, "max_days": 2, "lineup": lineup}, **changes)


def all_games(report: str) -> dict[str, list[str]]:
    """The cells of each row of the report's tables for all games, by the row's first cell."""
    section = report.split("## All games")[1].split("\n## ", maxsplit=1)[0]
    rows = (row.strip("| ").split(" | ") for row in section.splitlines() if row.startswith("| "))
    return {first: rest for first, *rest in rows}


def test_the_cells_are_every_combination_of_the_axes_on_the_same_seeds() -> None:
    matrix = tiny(
        first_seed=5,
        axes={"murderers": [1, 2], "lineup.everyone.effort": ["low", "high"]},
        base={"residents": 8, "lineup": {"seats": {"0": {"provider": "prober"}}}},
    )

    cells = matrix.cells()

    assert [cell.name for cell in cells] == [
        "murderers=1, lineup.everyone.effort=low",
        "murderers=1, lineup.everyone.effort=high",
        "murderers=2, lineup.everyone.effort=low",
        "murderers=2, lineup.everyone.effort=high",
    ]
    config = cells[3].config(seed=6)
    assert (config.murderers, config.lineup.everyone.effort) == (2, Effort.HIGH)
    assert (config.residents, config.lineup.seats, config.seed) == (8, {0: PROBER}, 6)
    assert config.open_floor_seconds is None  # games compare on Statements, not on time
    assert [(cell.index, seed) for cell, seed in matrix.games()][:5] == [
        (0, 5),
        (1, 5),
        (2, 5),
        (3, 5),
        (0, 6),  # every cell plays a seed before any plays the next
    ]


@pytest.mark.parametrize(
    ("changes", "problem"),
    [
        ({"axes": {"murderers": [1, 2]}}, "more than a quarter"),  # 2 Murderers among 6
        ({"axes": {"detective_skill": [1]}}, "detective_skill"),
        ({"base": {"seed": 3}}, "first_seed"),
        ({"base": {"open_floor_seconds": 60}}, "Open floor"),
        ({"games": 3}, "games"),
    ],
    ids=["breaks the rules", "unknown axis", "a seed", "a time limit", "unknown key"],
)
def test_a_matrix_that_cannot_be_played_is_refused_before_any_game(
    changes: dict[str, Any], problem: str
) -> None:
    with pytest.raises(ValidationError, match=problem):
        tiny(**changes).cells()


def test_a_matrix_is_read_from_toml(tmp_path: Path) -> None:
    file = tmp_path / "matrix.toml"
    file.write_text(
        'name = "tiny"\ngames_per_cell = 2\n[base]\nresidents = 6\nmurderers = 1\n'
        '[base.lineup.seats.0]\nprovider = "prober"\n[axes]\nmax_days = [2, 3]\n'
        "[caps]\ngames_per_batch = 3\npause_seconds = 1.5\n",
        encoding="utf-8",
    )

    matrix = Matrix.read(file)

    assert [cell.config(seed=1).max_days for cell in matrix.cells()] == [2, 3]
    assert matrix.cells()[0].config(seed=1).lineup.seats == {0: PROBER}
    assert (matrix.caps.games_per_batch, matrix.caps.pause_seconds) == (3, 1.5)


def games_in(folder: Path) -> list[tuple[int, int, str]]:
    """Each game the run has played, by cell and seed, with its whole log."""
    run = RunFolder(folder)
    return [(game.cell, game.seed, run.file_of(game).read_text()) for game in run.played()]


async def test_a_run_played_in_capped_batches_holds_the_same_games_as_one_played_at_once(
    tmp_path: Path,
) -> None:
    capped = tiny(caps={"games_per_batch": 3})

    first = await play_batch(capped, tmp_path / "capped", SCRIPTED_ONLY)
    second = await play_batch(capped, tmp_path / "capped", SCRIPTED_ONLY)
    whole = await play_batch(tiny(), tmp_path / "whole", SCRIPTED_ONLY)

    assert (first, second, whole) == (
        Batch(3, "capped"),
        Batch(1, "complete"),
        Batch(4, "complete"),
    )
    assert games_in(tmp_path / "capped") == games_in(tmp_path / "whole")
    assert len(games_in(tmp_path / "whole")) == 4
    played = RunFolder(tmp_path / "whole").played()
    tags = {(game.prompt_version, game.commit, game.uncommitted_changes) for game in played}
    assert tags == {(prompt_version(), *code_version())}


async def test_a_batch_pauses_between_games(tmp_path: Path) -> None:
    pauses: list[float] = []

    async def pause(seconds: float) -> None:
        pauses.append(seconds)

    await play_batch(tiny(caps={"pause_seconds": 1.5}), tmp_path, SCRIPTED_ONLY, pause=pause)

    assert pauses == [1.5, 1.5, 1.5]  # four games, and none waits before the first


async def test_an_aborted_game_stops_the_batch_and_is_played_again_when_the_run_goes_on(
    tmp_path: Path,
) -> None:
    out_of_quota = {"claude": FakeModel(lambda request: ModelReply.failure("rate limited"))}

    stopped = await play_batch(on_claude(), tmp_path, out_of_quota)
    resumed = await play_batch(on_claude(), tmp_path, {"claude": FakeModel()})

    assert (stopped.played, stopped.stopped) == (0, "aborted")
    assert "rate limited" in stopped.reason
    assert resumed == Batch(4, "complete")
    assert len(games_in(tmp_path)) == 4


async def test_a_run_plays_one_batch_at_a_time(tmp_path: Path) -> None:
    with (
        RunFolder(tmp_path).playing(),  # another batch is playing this run
        pytest.raises(RunBusyError, match="another batch"),
    ):
        await play_batch(tiny(), tmp_path, SCRIPTED_ONLY)

    finished = await play_batch(tiny(), tmp_path, SCRIPTED_ONLY)
    again = await play_batch(tiny(), tmp_path, SCRIPTED_ONLY)

    assert finished == Batch(4, "complete")  # once it is done, the run is free again
    assert again == Batch(0, "complete")  # and free once the batch that played it has ended


async def test_a_run_goes_on_only_with_the_matrix_it_began_with(tmp_path: Path) -> None:
    await play_batch(tiny(caps={"games_per_batch": 1}), tmp_path, SCRIPTED_ONLY)

    with pytest.raises(MatrixChangedError):
        await play_batch(tiny(first_seed=9), tmp_path, SCRIPTED_ONLY)
    resumed = await play_batch(tiny(caps={"games_per_batch": 5}), tmp_path, SCRIPTED_ONLY)

    assert resumed == Batch(3, "complete")  # caps may change between batches


async def test_the_report_gives_every_rate_with_its_interval_and_sample_sizes(
    tmp_path: Path,
) -> None:
    await play_batch(tiny(), tmp_path, SCRIPTED_ONLY)

    report = write_report(tmp_path).read_text(encoding="utf-8")

    rows = all_games(report)
    labels = [field.description for field in Measures.model_fields.values() if field.description]
    for label in labels:
        rate, interval, trials, _ = rows[label]
        assert ("%" in rate and " to " in interval) == (trials != "0*"), label  # none: no rate
    assert rows["Town win rate"][2:] == ["4*", "4*"]  # too few trials and games: marked
    assert rows["Seat"] == ["Accused", "95% interval", "Trials", "Games", "By chance"]
    assert "below 30" in report and "about 100 games" in report
    commit = RunFolder(tmp_path).played()[0].commit
    assert commit[:12] in report and prompt_version() in report
    every_game = report.split("## Every game")[1]
    assert every_game.count("](games/cell") == 4  # each game's winner, Days and file


async def test_the_report_charts_town_win_rate_against_the_rules_the_games_varied(
    tmp_path: Path,
) -> None:
    await play_batch(tiny(), tmp_path, SCRIPTED_ONLY)

    report = write_report(tmp_path).read_text(encoding="utf-8")

    by_accuracy = (tmp_path / "charts" / "town-win-rate-by-detective-accuracy.svg").read_text()
    assert by_accuracy.count("<circle") == 2  # one point per accuracy the matrix plays
    assert "<title>" in by_accuracy
    assert not (tmp_path / "charts" / "town-win-rate-by-murderers.svg").exists()
    assert "Not charted: every game played had the same Murderers (1)." in report


async def test_the_report_flags_games_played_by_different_prompts(tmp_path: Path) -> None:
    await play_batch(tiny(), tmp_path, SCRIPTED_ONLY)
    ledger = tmp_path / "games.ndjson"
    first, *rest = ledger.read_text().splitlines(keepends=True)
    ledger.write_text("".join([first.replace(prompt_version(), "0123456789ab"), *rest]))

    report = write_report(tmp_path).read_text(encoding="utf-8")

    assert "0123456789ab" in report and "different code or prompts" in report


async def test_the_report_measures_the_model_calls_of_agents(tmp_path: Path) -> None:
    await play_batch(on_claude(games_per_cell=1), tmp_path, {"claude": FakeModel()})

    rows = all_games(write_report(tmp_path).read_text(encoding="utf-8"))

    for measurement in (
        "Model calls per game",
        "Prompt tokens per game",
        "Read from the cache",
        "Equivalent cost per game",
        "Latency",
    ):
        assert measurement in rows


def test_percentiles_are_nearest_rank() -> None:
    hundred = list(range(1, 101))

    assert (percentile(hundred, 50), percentile(hundred, 95)) == (50, 95)
    assert percentile([30, 10, 20], 50) == 20
    assert percentile([7], 95) == 7
    assert percentile([], 50) is None


def test_mm_evaluate_plays_the_smoke_matrix_ci_runs_and_reports_it(tmp_path: Path) -> None:
    evaluated = CliRunner().invoke(
        app, ["evaluate", str(MATRICES / "smoke.toml"), "--out", str(tmp_path)]
    )

    assert evaluated.exit_code == 0, evaluated.output
    assert "Every game is played" in evaluated.output
    rows = all_games((tmp_path / "report.md").read_text(encoding="utf-8"))
    reveals = next(cells for label, cells in rows.items() if label.startswith("Injection"))
    assert reveals[2] != "0*"  # the prober in seat 0 probed the Murderers


def test_mm_evaluate_refuses_a_matrix_it_cannot_play(tmp_path: Path) -> None:
    broken = tmp_path / "broken.toml"
    broken.write_text('name = "broken"\ngames_per_cell = 1\n[axes]\nmurderers = [4]\n')

    refused = CliRunner().invoke(app, ["evaluate", str(broken), "--out", str(tmp_path / "run")])

    assert refused.exit_code != 0
    assert not (tmp_path / "run").exists()


@pytest.mark.parametrize("file", sorted(MATRICES.glob("*.toml")), ids=lambda file: file.stem)
def test_every_matrix_checked_in_can_be_played(file: Path) -> None:
    assert Matrix.read(file).cells()
