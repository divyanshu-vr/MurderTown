"""An evaluation's report: what came of every game a run has played so far.

Each game's measures are read again from its files, so the report always agrees with the games
the console replays, and a change to a measure applies to runs already played. Rates pool all
their trials and come with their 95% Wilson interval and how many trials and games they rest on.
What the model calls used and how long they took are measurements, given without an interval:
a game's tokens and seconds are counted, not sampled.
"""

import math
from collections.abc import Callable, Hashable, Sequence
from dataclasses import dataclass
from pathlib import Path

from mm.agents import Cost, ModelCall
from mm.cli.charts import Point, rate_chart
from mm.cli.evaluation import Played, RunFolder
from mm.cli.matrix import Cell
from mm.cli.recording import calls_beside, read_ndjson
from mm.cli.transcript import SIDES
from mm.engine import GameConfig
from mm.engine.events import Event
from mm.review.measures import Measures, SeatAccusations, measures_of
from mm.review.rates import Rate

FEW = 30
"""Fewer trials or games than this, and a rate's interval is too wide to say much: marked *."""

CAVEATS = f"""\
- **Few trials or games.** A count below {FEW} is marked *: a rate resting on it has a wide
  interval.
- **Games are the sample.** Most rates count many trials in each game, and the trials of one
  game are not independent (the same Residents, the same Days), so their intervals are narrower
  than they should be. How many games a rate rests on is the honest size of its sample.
- **How many games it takes.** Telling two town win rates 20 points apart takes about 100 games
  in each cell (95% confidence, 80% power); 10 points apart, about 400.
- **Measurements** of the model calls (tokens, the cache, cost, latency) are counted, not
  sampled, so they carry no interval.
- **Scripted bots** play at random: their behaviour (Lies, herding, Influence, hallucinated
  claims, reveals, position bias) means something only where Agents play.
- **Herding** by chance alone puts about one ballot in as many as there are living Residents
  against the first accused.
- **Injection probes.** A prober takes a seat wherever the lineup names one, and its own
  Statements, ballots and decisions count among its cell's, so a cell with probes compares with
  one without only on what the probe measures.
- **Hallucinated claims** are found by a heuristic: Statements that speak to the dead, accuse
  the dead whose death showed them innocent, or name someone from the town's pool of names who
  never lived in it.
- **Position bias.** Seats keep their roles across cells that share seeds and the number of
  Residents, so with few seeds a seat's role and its position are hard to tell apart.
"""

CHARTED: dict[str, Callable[[GameConfig], Hashable]] = {
    "Detective accuracy": lambda config: config.detective_accuracy,
    "Murderers": lambda config: config.murderers,
}
"""The Rules town win rate is charted against, every other Rule pooled."""


@dataclass(frozen=True)
class PlayedGame:
    """One game of the run, read back from its files."""

    played: Played
    config: GameConfig
    measures: Measures
    calls: list[ModelCall]


def write_report(folder: Path) -> Path:
    """Write the report of the run in `folder` (and its charts), and say where."""
    run = RunFolder(folder)
    matrix = run.matrix()
    cells = matrix.cells()
    games = [_read(run, played, cells) for played in run.played()]
    lines = [
        f"# Evaluation: {matrix.name}",
        "",
        f"{len(games)} of {len(cells) * matrix.games_per_cell} games played: {len(cells)} "
        f"cells of {matrix.games_per_cell} games, each on seeds {matrix.first_seed} to "
        f"{matrix.first_seed + matrix.games_per_cell - 1}.",
        "",
        *_versions(games),
        "## Caveats",
        "",
        CAVEATS,
        "## All games",
        "",
        *_summary(games),
        "### Position bias",
        "",
        "How often the Resident in each seat was accused, out of the accusations made while",
        "they could have been, beside how often chance alone would have named them.",
        "",
        *_position_bias(games),
    ]
    for rule, value_of in CHARTED.items():
        lines += [f"## Town win rate by {rule}", "", _chart(folder, rule, value_of, games), ""]
    for cell in cells:
        in_cell = [game for game in games if game.played.cell == cell.index]
        lines += [f"## Cell {cell.index}: {cell.name}", "", *_summary(in_cell)]
    lines += ["## Every game", "", *_every_game(games)]
    report = folder / "report.md"
    report.write_text("\n".join(lines), encoding="utf-8", newline="\n")
    return report


def _read(run: RunFolder, played: Played, cells: Sequence[Cell]) -> PlayedGame:
    file = run.file_of(played)
    calls = calls_beside(file)
    return PlayedGame(
        played=played,
        config=cells[played.cell].config(played.seed),
        measures=measures_of(read_ndjson(file, Event)),
        calls=read_ndjson(calls, ModelCall) if calls.exists() else [],
    )


def _versions(games: Sequence[PlayedGame]) -> list[str]:
    commits = sorted({_commit(game.played) for game in games})
    prompts = sorted({game.played.prompt_version for game in games})
    lines = [f"Played at commit {', '.join(commits)}, with prompts {', '.join(prompts)}.", ""]
    if len(commits) > 1 or len(prompts) > 1:
        lines += ["> **Games were played by different code or prompts**: compare with care.", ""]
    return lines


def _commit(played: Played) -> str:
    changes = " (with uncommitted changes)" if played.uncommitted_changes else ""
    return played.commit[:12] + changes


def _summary(games: Sequence[PlayedGame]) -> list[str]:
    if not games:
        return ["No games played yet.", ""]
    return [*_rates(games), *_measurements(games)]


def _rates(games: Sequence[PlayedGame]) -> list[str]:
    rows = ["| Measure | Rate | 95% interval | Trials | Games |", "|---|---|---|---|---|"]
    by_game = [game.measures.rates() for game in games]
    for label in by_game[0]:
        rates = [rates[label] for rates in by_game]
        counted = sum(rate.trials > 0 for rate in rates)
        rows.append(f"| {label} | {_rate_cells(_pooled(rates))} | {_count(counted)} |")
    return [*rows, ""]


def _measurements(games: Sequence[PlayedGame]) -> list[str]:
    days = sum(game.measures.days for game in games) / len(games)
    rows = ["| Measurement | Value |", "|---|---|", f"| Days per game | {days:.1f} |"]
    calls = [call for game in games for call in game.calls]
    if not calls:
        return [*rows, "", "No model calls: scripted bots played every seat.", ""]
    cost, per_game = Cost.of(calls), len(games)
    latencies = [call.latency_ms for call in calls]
    rows += [
        f"| Model calls per game | {cost.calls / per_game:,.1f} |",
        f"| Prompt tokens per game | {cost.prompt_tokens / per_game:,.0f} |",
        f"| Output tokens per game | {cost.output_tokens / per_game:,.0f} |",
        f"| Read from the cache | {_percent(cost.cache_hit_rate)} of prompt tokens |",
        f"| Equivalent cost per game | ${cost.cost_usd / per_game:,.4f} |",
        f"| Latency | median {percentile(latencies, 50):,.0f} ms, "
        f"95th percentile {percentile(latencies, 95):,.0f} ms, over {len(calls):,} calls |",
    ]
    return [*rows, ""]


def _position_bias(games: Sequence[PlayedGame]) -> list[str]:
    seats: dict[int, SeatAccusations] = {}
    games_of: dict[int, int] = {}
    for game in games:
        for seat in game.measures.seats:
            seats[seat.seat] = seats[seat.seat] + seat if seat.seat in seats else seat
            games_of[seat.seat] = games_of.get(seat.seat, 0) + (seat.accused.trials > 0)
    rows = [
        "| Seat | Accused | 95% interval | Trials | Games | By chance |",
        "|---|---|---|---|---|---|",
    ]
    for number, seat in sorted(seats.items()):
        chance = seat.by_chance / seat.accused.trials if seat.accused.trials else None
        rows.append(
            f"| {number} | {_rate_cells(seat.accused)} | {_count(games_of[number])} "
            f"| {_percent(chance)} |"
        )
    return [*rows, ""]


def _chart(
    folder: Path,
    rule: str,
    value_of: Callable[[GameConfig], Hashable],
    games: Sequence[PlayedGame],
) -> str:
    """Chart town win rate against one Rule, if the games played more than one value of it;
    what the report shows of it, either way."""
    by_value: dict[Hashable, list[PlayedGame]] = {}
    for game in games:
        by_value.setdefault(value_of(game.config), []).append(game)
    if len(by_value) < 2:
        values = ", ".join(map(str, by_value)) or "none yet"
        return f"Not charted: every game played had the same {rule} ({values})."
    points = [
        Point(str(value), _pooled([game.measures.town_won for game in group]), len(group))
        for value, group in sorted(by_value.items(), key=lambda item: str(item[0]))
    ]
    path = Path("charts") / f"town-win-rate-by-{rule.lower().replace(' ', '-')}.svg"
    (folder / path).parent.mkdir(parents=True, exist_ok=True)
    chart = rate_chart(f"Town win rate by {rule}", rule, points)
    (folder / path).write_text(chart, encoding="utf-8", newline="\n")
    return f"![Town win rate by {rule}]({path.as_posix()})"


def _every_game(games: Sequence[PlayedGame]) -> list[str]:
    rows = ["| Cell | Seed | Winner | Days | Game file |", "|---|---|---|---|---|"]
    for game in games:
        winner = SIDES[game.measures.winner] if game.measures.winner else "–"
        file = game.played.file
        rows.append(
            f"| {game.played.cell} | {game.played.seed} | {winner} | {game.measures.days} "
            f"| [{file}]({file}) |"
        )
    return [*rows, ""]


def _pooled(rates: Sequence[Rate]) -> Rate:
    return sum(rates, start=Rate())


def _rate_cells(rate: Rate) -> str:
    """A rate, its interval and its trials, as three cells of a table."""
    if rate.value is None or rate.interval is None:
        return f"– | – | {_count(rate.trials)}"
    low, high = rate.interval
    return f"{_percent(rate.value)} | {_percent(low)} to {_percent(high)} | {_count(rate.trials)}"


def _count(count: int) -> str:
    return f"{count}*" if count < FEW else str(count)


def _percent(share: float | None) -> str:
    return "–" if share is None else f"{share:.1%}"


def percentile(values: Sequence[float], percent: int) -> float | None:
    """The smallest value with at least `percent`% of the values at or below it (nearest rank)."""
    if not values:
        return None
    rank = math.ceil(percent / 100 * len(values))
    return sorted(values)[max(rank, 1) - 1]
