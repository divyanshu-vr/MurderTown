"""Rules of Discussion: who speaks next on the Open floor, and whom a Statement names.

On the Open floor every living Resident bids how urgently they want to speak.
The highest bid speaks. A tie is drawn at random, but a Resident addressed by
the previous Statement is three times as likely to win it, so being addressed
tends to earn a reply. If every bid is 0, nobody speaks that Turn.
"""

from collections.abc import Collection, Iterable, Mapping
from random import Random

from mm.engine.config import GameConfig
from mm.engine.state import GameState

ADDRESSED_WEIGHT = 3
"""How much likelier a Resident the previous Statement addressed is to win a tied bid."""


def speaker_for(bids: Mapping[str, int], addressed: Collection[str], rng: Random) -> str | None:
    """Who makes the next Statement, given each Resident's bid; None if nobody wants to."""
    if not bids or max(bids.values()) == 0:
        return None
    top = max(bids.values())
    tied = [name for name, urgency in bids.items() if urgency == top]
    weights = [ADDRESSED_WEIGHT if name in addressed else 1 for name in tied]
    return rng.choices(tied, weights=weights)[0]


def named(names: Iterable[str], state: GameState, speaker: str) -> tuple[str, ...]:
    """The real Residents a Statement names, each once, never the speaker themselves."""
    residents = {resident.name for resident in state.residents} - {speaker}
    return tuple(dict.fromkeys(name for name in names if name in residents))


QUIET_TURNS_TO_END = 2
"""The Open floor ends after this many Turns in a row in which nobody wanted to speak."""


def open_floor_over(
    config: GameConfig, statements_made: int, quiet_turns: int, seconds_elapsed: float
) -> bool:
    """Whether the Open floor has reached any of its three limits."""
    out_of_time = (
        config.open_floor_seconds is not None and seconds_elapsed >= config.open_floor_seconds
    )
    return (
        statements_made >= config.open_floor_statements
        or quiet_turns >= QUIET_TURNS_TO_END
        or out_of_time
    )
