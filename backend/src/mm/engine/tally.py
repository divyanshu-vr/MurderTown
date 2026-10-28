"""Counting choices and breaking ties with the game's seeded random source.

The Open floor's next speaker and the Murderers' Victim are both the top
choice, with a tie drawn at random, so a replayed game breaks every tie the
same way.
"""

from collections import Counter
from collections.abc import Callable, Iterable, Mapping
from random import Random


def drawn_from_the_top(
    scores: Mapping[str, int], rng: Random, weight: Callable[[str], int] = lambda _: 1
) -> str:
    """The name with the highest score; a tie is drawn at random, each name weighted by `weight`."""
    top = max(scores.values())
    tied = [name for name, score in scores.items() if score == top]
    return rng.choices(tied, weights=[weight(name) for name in tied])[0]


def plurality(choices: Iterable[str], rng: Random) -> str:
    """The most chosen name, with a tie drawn at random."""
    return drawn_from_the_top(Counter(choices), rng)
