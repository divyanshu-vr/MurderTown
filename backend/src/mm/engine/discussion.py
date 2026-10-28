"""Rules of Discussion: who speaks next on the Open floor, and when the Open floor is over.

On the Open floor every living Resident bids how urgently they want to speak.
The highest bid speaks. A tie is drawn at random, but a Resident addressed by
the previous Statement is three times as likely to win it, so being addressed
tends to earn a reply. If every bid is 0, nobody speaks that Turn.
"""

from collections.abc import Collection, Mapping
from random import Random
from typing import Literal

from mm.engine.config import GameConfig
from mm.engine.tally import drawn_from_the_top

ADDRESSED_WEIGHT = 3
"""How much likelier a Resident the previous Statement addressed is to win a tied bid."""


def speaker_for(bids: Mapping[str, int], addressed: Collection[str], rng: Random) -> str | None:
    """Who makes the next Statement, given each Resident's bid; None if nobody wants to."""
    if not bids or max(bids.values()) == 0:
        return None
    return drawn_from_the_top(bids, rng, lambda name: ADDRESSED_WEIGHT if name in addressed else 1)


QUIET_TURNS_TO_END = 2
"""The Open floor ends after this many Turns in a row in which nobody wanted to speak."""


OpenFloorLimit = Literal["statements", "quiet", "time"]


def open_floor_limit(
    config: GameConfig, statements_made: int, quiet_turns: int, out_of_time: bool
) -> OpenFloorLimit | None:
    """Which of its three limits ended the Open floor, or None while it goes on. Whether
    its time is up is for the caller to say: the engine reads no clock."""
    if statements_made >= config.open_floor_statements:
        return "statements"
    if quiet_turns >= QUIET_TURNS_TO_END:
        return "quiet"
    return "time" if out_of_time else None
