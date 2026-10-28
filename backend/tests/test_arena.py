"""The model arena: Contenders play each other from both sides on the same seeds, and a
leaderboard reports how they did, with confidence intervals, cost and latency.
"""

import math
from collections import Counter
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from mm.agents import ModelCall
from mm.cli.evaluation import RunFolder, play_batch
from mm.cli.leaderboard import RATED_FROM, ArenaGame, Play, leaderboard, ratings_of
from mm.cli.matrix import Matrix
from mm.cli.recording import calls_beside, read_ndjson
from mm.cli.report import write_report
from mm.engine import PlayedBy, Role
from mm.engine.casting import seated_roles
from mm.llm import ModelReply, ModelRequest, Usage
from tests.support import FakeModel, sensible_answer

HAIKU = {"provider": "claude", "model": "claude-haiku-5-5", "effort": "low"}
SONNET = {"provider": "anthropic", "model": "claude-sonnet-5-5", "effort": "low"}


def arena(**changes: Any) -> Matrix:
    """Haiku against Sonnet, each from both sides, in small short games."""
    matrix: dict[str, Any] = {
        "name": "arena",
        "games_per_cell": 2,
        "base": {"residents": 8, "murderers": 2, "max_days": 1},
        "contenders": [HAIKU, SONNET],
    }
    return Matrix.model_validate(matrix | changes)


def test_an_arena_plays_every_contender_against_every_other_from_both_sides() -> None:
    cells = arena().cells()

    assert [cell.name for cell in cells] == [
        "Murderers: claude-haiku-5-5 (low effort, claude), "
        "Town: claude-haiku-5-5 (low effort, claude)",
        "Murderers: claude-haiku-5-5 (low effort, claude), "
        "Town: claude-sonnet-5-5 (low effort, anthropic)",
        "Murderers: claude-sonnet-5-5 (low effort, anthropic), "
        "Town: claude-haiku-5-5 (low effort, claude)",
        "Murderers: claude-sonnet-5-5 (low effort, anthropic), "
        "Town: claude-sonnet-5-5 (low effort, anthropic)",
    ]
    lineup = cells[1].config(seed=1).lineup
    assert (lineup.murderers, lineup.town) == (PlayedBy(**HAIKU), PlayedBy(**SONNET))


def test_every_contender_plays_every_role_and_side_equally_often() -> None:
    matrix = arena(axes={"residents": [8, 12]})

    roles: dict[PlayedBy, Counter[Role]] = {}
    sides: dict[PlayedBy, Counter[str]] = {}
    for cell, seed in matrix.games():
        config = cell.config(seed)
        for seat, role in seated_roles(config).items():
            played_by = config.lineup.played_by(seat, role.side)
            roles.setdefault(played_by, Counter())[role] += 1
        sides.setdefault(config.lineup.murderers or PlayedBy(), Counter())["Murderers"] += 1
        sides.setdefault(config.lineup.town or PlayedBy(), Counter())["Town"] += 1

    haiku, sonnet = PlayedBy(**HAIKU), PlayedBy(**SONNET)
    assert roles[haiku] == roles[sonnet]
    assert set(roles[haiku]) == set(Role)
    assert sides[haiku] == sides[sonnet] == Counter(Murderers=8, Town=8)


@pytest.mark.parametrize(
    ("changes", "problem"),
    [
        ({"contenders": [HAIKU]}, "at least two"),
        ({"contenders": [HAIKU, HAIKU]}, "twice"),
        ({"axes": {"lineup.town.effort": ["low", "high"]}}, "lineup.town"),
        (
            {"base": {"residents": 8, "lineup": {"seats": {"0": {"provider": "prober"}}}}},
            "lineup.seats",
        ),
        ({"axes": {"lineup": [{"seats": {"0": {"provider": "prober"}}}]}}, "lineup"),
    ],
    ids=["one contender", "the same one twice", "a side's axis", "a seat", "the whole lineup"],
)
def test_an_arena_that_would_not_be_fair_is_refused(changes: dict[str, Any], problem: str) -> None:
    with pytest.raises(ValidationError, match=problem):
        arena(**changes)


def test_bradley_terry_rates_a_contender_who_won_two_games_in_three_higher() -> None:
    ratings = ratings_of([("a", "b"), ("a", "b"), ("b", "a")])

    # With one imagined win and loss between them, a has won 3 of 5: strengths 3 to 2.
    assert ratings["a"] - ratings["b"] == pytest.approx(400 * math.log10(3 / 2), abs=0.01)
    assert (ratings["a"] + ratings["b"]) / 2 == pytest.approx(1500)


def test_ratings_follow_who_beat_whom_and_stay_finite_for_a_contender_who_never_won() -> None:
    ratings = ratings_of([("a", "b"), ("a", "b"), ("b", "c"), ("b", "c"), ("a", "c")])

    assert ratings["a"] > ratings["b"] > ratings["c"]
    assert math.isfinite(ratings["c"])


def answering_in(latency_ms: int, name: str) -> FakeModel:
    """A fake model, named unlike the provider the lineup knows it by, that takes `latency_ms`
    and a thousand tokens over every answer, so whose calls are whose shows."""

    def respond(request: ModelRequest) -> ModelReply:
        usage = Usage(input_tokens=1000, output_tokens=100)
        return replace(sensible_answer(request), usage=usage, latency_ms=latency_ms)

    return FakeModel(respond, name=name)


def fakes() -> dict[str, FakeModel]:
    return {
        "claude": answering_in(200, "fake-haiku"),
        "anthropic": answering_in(900, "fake-sonnet"),
    }


def table_rows(report: str, heading: str) -> dict[str, list[str]]:
    """The cells of each row of the first table under a heading, by the row's first cell."""
    section = report.split(heading)[1].split("\n#", maxsplit=1)[0]
    rows = (row.strip("| ").split(" | ") for row in section.splitlines() if row.startswith("| "))
    return {first: rest for first, *rest in rows}


HAIKU_NAME = "claude-haiku-5-5 (low effort, claude)"
SONNET_NAME = "claude-sonnet-5-5 (low effort, anthropic)"


async def test_the_leaderboard_gives_each_contenders_win_rate_with_its_interval_cost_and_latency(
    tmp_path: Path,
) -> None:
    await play_batch(arena(games_per_cell=1), tmp_path, fakes())

    report = write_report(tmp_path).read_text(encoding="utf-8")

    rows = table_rows(report, "## Leaderboard")
    haiku, sonnet = rows[HAIKU_NAME], rows[SONNET_NAME]
    for won, interval, games, *_ in (haiku, sonnet):
        assert "%" in won and " to " in interval and games == "2*"  # against the other only
    assert haiku[-1].startswith("200 ms") and sonnet[-1].startswith("900 ms")  # its own calls
    haiku_cost, sonnet_cost = (float(row[-2].lstrip("$")) for row in (haiku, sonnet))
    assert 0 < haiku_cost < sonnet_cost  # the same tokens cost more on Sonnet
    assert f"Ratings appear from {RATED_FROM} games" in report
    sides = table_rows(report, "### The Town's win rate, by who played each side")
    assert all(" to " in cell for cell in sides[HAIKU_NAME] + sides[SONNET_NAME])


async def test_contenders_get_the_same_prompts(tmp_path: Path) -> None:
    await play_batch(arena(games_per_cell=1), tmp_path, fakes())

    run = RunFolder(tmp_path)
    first: list[ModelCall] = []
    for game in run.played():
        first.append(read_ndjson(calls_beside(run.file_of(game)), ModelCall)[0])
    _, haiku_first, sonnet_first, _ = first  # the two games where each plays the other

    assert (haiku_first.system, haiku_first.prompt) == (sonnet_first.system, sonnet_first.prompt)
    assert haiku_first.model != sonnet_first.model


async def test_only_games_whose_every_pairing_was_played_count_on_the_leaderboard(
    tmp_path: Path,
) -> None:
    await play_batch(arena(games_per_cell=1, caps={"games_per_batch": 3}), tmp_path, fakes())

    report = write_report(tmp_path).read_text(encoding="utf-8")

    assert "0 arena games count" in report
    assert "3 games wait for the rest of their group" in report


def test_ratings_appear_labelled_approximate_once_enough_games_were_played() -> None:
    haiku, sonnet = PlayedBy(**HAIKU), PlayedBy(**SONNET)

    def game(group: int, murderers: PlayedBy, town: PlayedBy, town_won: bool) -> ArenaGame:
        def play(contender: PlayedBy, won: bool) -> Play:
            return Play(contender, won, calls=(), decisions=0, fallbacks=0)

        return ArenaGame(
            (f"group {group}", 1, "v1"), play(murderers, not town_won), play(town, town_won)
        )

    games = [
        played
        for group in range(RATED_FROM // 2)  # two games between the Contenders in each group
        for played in (
            game(group, haiku, haiku, town_won=True),
            game(group, haiku, sonnet, town_won=group % 3 == 0),  # Haiku wins two in three
            game(group, sonnet, haiku, town_won=True),
            game(group, sonnet, sonnet, town_won=False),
        )
    ]

    lines = leaderboard([haiku, sonnet], games)

    rated = table_rows("\n".join(lines), "### Ratings (approximate)")
    assert float(rated[HAIKU_NAME][0]) > 1500 > float(rated[SONNET_NAME][0])
