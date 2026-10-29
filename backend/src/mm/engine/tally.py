"""Counting choices and breaking ties with the game's seeded random source.

The Murderers' Victim is the top choice of their kill votes, with a tie drawn at
random, so a replayed game breaks every tie the same way.
"""

from collections import Counter
from collections.abc import Iterable
from random import Random


def plurality(choices: Iterable[str], rng: Random) -> str:
    """The most chosen name, with a tie drawn at random."""
    counts = Counter(choices)
    top = max(counts.values())
    return rng.choices([name for name, count in counts.items() if count == top])[0]
