"""Rules of the Vote: who may be voted for, and who is banished.

Ballots are sealed: every Resident chooses before any ballot is revealed. The
Resident with the most ballots is banished only if they beat SKIP outright;
a tie, at the top or with SKIP, banishes nobody.
"""

from collections import Counter
from collections.abc import Iterable
from dataclasses import dataclass

from mm.engine.decisions import SKIP
from mm.engine.state import GameState


@dataclass(frozen=True)
class VoteOutcome:
    tally: dict[str, int]
    skips: int
    banished: str | None


def ballot_options(state: GameState, voter: str) -> tuple[str, ...]:
    """Every other living Resident, plus SKIP."""
    return (*[name for name in state.living if name != voter], SKIP)


def target_of(choice: str) -> str | None:
    """The Resident a ballot choice names, or None for SKIP."""
    return None if choice == SKIP else choice


def tally_ballots(choices: Iterable[str]) -> VoteOutcome:
    counts = Counter(choices)
    skips = counts.pop(SKIP, 0)
    ranked = counts.most_common()
    tally = dict(sorted(counts.items()))
    if not ranked:
        return VoteOutcome(tally=tally, skips=skips, banished=None)

    leader, votes = ranked[0]
    tied_at_the_top = len(ranked) > 1 and ranked[1][1] == votes
    banished = leader if votes > skips and not tied_at_the_top else None
    return VoteOutcome(tally=tally, skips=skips, banished=banished)
