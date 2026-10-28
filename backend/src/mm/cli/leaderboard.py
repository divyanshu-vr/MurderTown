"""The arena's leaderboard: how each Contender did against the others.

A Contender plays a side of an arena game; its model calls and fallbacks are those of the
Residents on that side (the narrator has no side, so it counts for neither). Only the games of
complete mirror groups count: every pairing of Contenders played on the same conditions and
seed, by the same prompts. So each Contender has played as many games as the Murderers as the
Town, and the side that wins more often favours none of them.

Ratings come from a Bradley-Terry model: each Contender has a strength, and one beats another
with the chance of its strength out of both of theirs. Strengths are fitted to the games played
by the usual minorise-maximise iteration, and shown on an Elo-like scale. They are approximate,
so the report shows them only once enough games have been played.
"""

import math
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass
from itertools import combinations

from mm.agents import Cost, ModelCall
from mm.cli.evaluation import Played
from mm.cli.matrix import Cell, name_of
from mm.cli.tables import dollars, latency, rate_cells, rate_with_interval, share_of
from mm.engine import PlayedBy, Side
from mm.engine.events import DecisionFellBack, Event, RoleAssigned, payloads_of
from mm.review.rates import Rate

RATED_FROM = 300
"""How many games between Contenders the report needs before it shows ratings."""

FIT_ROUNDS = 1000
"""How many times the ratings' fit is refined: far more than a few Contenders need."""

ARENA_NOTES = """\
Win rates count games against the other Contenders, not against themselves. Games is how many
of those each played: as many as the Murderers as the Town. Fallbacks and cost count only the
Contender's own seats (the Murderers hold fewer than the Town); the narrator counts for neither.
Every model gets its prompts from the same templates, but on the subscription the Agent SDK
adds about a thousand tokens of its own to each, which the API does not
(docs/agent-sdk-findings.md).
"""
"""What the leaderboard says about how to read it."""

Pair = tuple[PlayedBy, PlayedBy]


@dataclass(frozen=True)
class Play:
    """How one Contender played one side of an arena game: whether it won, and its Agents'
    model calls, decisions and fallbacks."""

    contender: PlayedBy
    won: bool
    calls: tuple[ModelCall, ...]
    decisions: int
    fallbacks: int


@dataclass(frozen=True)
class ArenaGame:
    """One arena game, and its mirror group: the cell's conditions, the seed and the prompts,
    the same in the games of every pairing of Contenders that mirror it."""

    mirror_group: tuple[str, int, str]
    murderers: Play
    town: Play

    @property
    def against_itself(self) -> bool:
        return self.murderers.contender == self.town.contender


@dataclass(frozen=True)
class Standing:
    """One Contender's results in its games against the others."""

    contender: PlayedBy
    won: Rate
    won_as_murderers: Rate
    won_as_town: Rate
    fallbacks: Rate
    calls: tuple[ModelCall, ...]


def arena_game(
    cell: Cell,
    played: Played,
    winner: Side | None,
    events: Sequence[Event],
    calls: Sequence[ModelCall],
) -> ArenaGame | None:
    """The arena game a cell played, or None if Contenders did not play its sides."""
    lineup = cell.config(played.seed).lineup
    if lineup.murderers is None or lineup.town is None:
        return None
    side_of = {
        assigned.resident: assigned.role.side for assigned in payloads_of(events, RoleAssigned)
    }
    fell_back = Counter(
        side_of.get(fallback.resident) for fallback in payloads_of(events, DecisionFellBack)
    )

    def play(side: Side, contender: PlayedBy) -> Play:
        own = tuple(call for call in calls if side_of.get(call.resident) is side)
        decisions = len({call.decision_id for call in own})
        return Play(contender, winner is side, own, decisions, fell_back[side])

    return ArenaGame(
        mirror_group=(cell.conditions, played.seed, played.prompt_version),
        murderers=play(Side.MURDERERS, lineup.murderers),
        town=play(Side.TOWN, lineup.town),
    )


def leaderboard(contenders: Sequence[PlayedBy], games: Sequence[ArenaGame]) -> list[str]:
    """The report's leaderboard of an arena's games, as Markdown lines."""
    counted = _mirrored(games, len(contenders))
    waiting = len(games) - len(counted)
    lines = [
        f"{len(counted)} arena games count: those of complete mirror groups, where every pairing "
        "of Contenders has been played on the same conditions and seed, by the same prompts. "
        f"{waiting} {'game waits' if waiting == 1 else 'games wait'} for the rest of their group.",
        "",
        "| Contender | Win rate | 95% interval | Games | As the Murderers | As the Town "
        "| Fallbacks | Equivalent cost per game | Latency |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for standing in _standings(counted):
        cost = Cost.of(standing.calls).cost_usd / standing.won.trials
        lines.append(
            f"| {name_of(standing.contender)} | {rate_cells(standing.won)} "
            f"| {share_of(standing.won_as_murderers)} | {share_of(standing.won_as_town)} "
            f"| {share_of(standing.fallbacks)} | {dollars(cost)} | {latency(standing.calls)} |"
        )
    return [*lines, "", ARENA_NOTES, *_ratings(counted), *_sides(contenders, counted)]


def _mirrored(games: Sequence[ArenaGame], contenders: int) -> list[ArenaGame]:
    played = Counter(game.mirror_group for game in games)
    return [game for game in games if played[game.mirror_group] == contenders * contenders]


def _standings(games: Sequence[ArenaGame]) -> list[Standing]:
    """Each Contender's results against the others, most often winning first."""
    plays: dict[PlayedBy, list[tuple[Side, Play]]] = {}
    for game in games:
        if not game.against_itself:
            plays.setdefault(game.murderers.contender, []).append((Side.MURDERERS, game.murderers))
            plays.setdefault(game.town.contender, []).append((Side.TOWN, game.town))
    table = [_standing(contender, own) for contender, own in plays.items()]
    return sorted(table, key=lambda standing: -(standing.won.value or 0))


def _standing(contender: PlayedBy, plays: Sequence[tuple[Side, Play]]) -> Standing:
    own = [play for _, play in plays]
    return Standing(
        contender=contender,
        won=_won(own),
        won_as_murderers=_won([play for side, play in plays if side is Side.MURDERERS]),
        won_as_town=_won([play for side, play in plays if side is Side.TOWN]),
        fallbacks=Rate(
            successes=sum(play.fallbacks for play in own),
            trials=sum(play.decisions for play in own),
        ),
        calls=tuple(call for play in own for call in play.calls),
    )


def _won(plays: Sequence[Play]) -> Rate:
    return Rate(successes=sum(play.won for play in plays), trials=len(plays))


def _ratings(games: Sequence[ArenaGame]) -> list[str]:
    results = _results(games)
    if len(results) < RATED_FROM:
        return [
            f"Ratings appear from {RATED_FROM} games between Contenders: {len(results)} so far.",
            "",
        ]
    rows = ["### Ratings (approximate)", "", "| Contender | Bradley-Terry rating |", "|---|---|"]
    rated = sorted(ratings_of(results).items(), key=lambda item: -item[1])
    return [*rows, *(f"| {name_of(contender)} | {rating:.0f} |" for contender, rating in rated), ""]


def _sides(contenders: Sequence[PlayedBy], games: Sequence[ArenaGame]) -> list[str]:
    """How often the Town won, by who played each side (a Contender against itself gives the
    baseline), and how often each Contender beat each other one."""
    town_won, beat = _town_wins(games), _head_to_head(games)
    names = [name_of(contender) for contender in contenders]
    lines = [
        "### The Town's win rate, by who played each side",
        "",
        f"| Murderers / Town | {' | '.join(names)} |",
        f"|---|{'---|' * len(names)}",
    ]
    for murderers in contenders:
        rates = [town_won.get((murderers, town), Rate()) for town in contenders]
        cells = [rate_with_interval(rate, "games") for rate in rates]
        lines.append(f"| {name_of(murderers)} | {' | '.join(cells)} |")
    lines += [
        "",
        "### Head to head",
        "",
        "| Contender | Against | Won | 95% interval | Games |",
        "|---|---|---|---|---|",
    ]
    for one, other in combinations(contenders, 2):
        for first, second in ((one, other), (other, one)):
            won = beat.get((first, second), Rate())
            lines.append(f"| {name_of(first)} | {name_of(second)} | {rate_cells(won)} |")
    return [*lines, ""]


def _town_wins(games: Sequence[ArenaGame]) -> dict[Pair, Rate]:
    """How often the Town won, by (who played the Murderers, who played the Town)."""
    town_won: dict[Pair, Rate] = {}
    for game in games:
        pair = (game.murderers.contender, game.town.contender)
        _add(town_won, pair, Rate(successes=int(game.town.won), trials=1))
    return town_won


def _head_to_head(games: Sequence[ArenaGame]) -> dict[Pair, Rate]:
    """How often one Contender beat another, by (that Contender, the other), from either side."""
    beat: dict[Pair, Rate] = {}
    for winner, loser in _results(games):
        _add(beat, (winner, loser), Rate(successes=1, trials=1))
        _add(beat, (loser, winner), Rate(successes=0, trials=1))
    return beat


def _add(rates: dict[Pair, Rate], pair: Pair, rate: Rate) -> None:
    rates[pair] = rates.get(pair, Rate()) + rate


def _results(games: Sequence[ArenaGame]) -> list[Pair]:
    """Who beat whom in each game between two Contenders: (winner, loser)."""
    return [
        (game.murderers.contender, game.town.contender)
        if game.murderers.won
        else (game.town.contender, game.murderers.contender)
        for game in games
        if not game.against_itself
    ]


def ratings_of[C](results: Sequence[tuple[C, C]]) -> dict[C, float]:
    """Bradley-Terry ratings from (winner, loser) results: 1500 on average, and 400 points apart
    where one Contender is ten times as strong as the other. One imagined win and one imagined
    loss between every two Contenders keep the rating of one who never won finite."""
    names = list(dict.fromkeys(name for result in results for name in result))
    wins = Counter(winner for winner, _ in results)
    met = Counter(frozenset(result) for result in results)
    for pair in combinations(names, 2):
        wins.update(pair)
        met[frozenset(pair)] += 2
    strength = dict.fromkeys(names, 1.0)
    for _ in range(FIT_ROUNDS):
        fitted = {
            name: wins[name]
            / sum(
                met[frozenset((name, other))] / (strength[name] + strength[other])
                for other in names
                if other != name
            )
            for name in names
        }
        middle = math.exp(sum(map(math.log, fitted.values())) / len(fitted))
        strength = {name: value / middle for name, value in fitted.items()}
    return {name: 1500 + 400 * math.log10(value) for name, value in strength.items()}
