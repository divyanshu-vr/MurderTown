"""Rules of Dusk: who talks to whom, and who speaks next in a Conversation.

Each Resident who wants to talk names up to three partners, most wanted first.
The askers are taken in a random order, and each gets their first preference who
is still free. A Resident is in one Conversation a Dusk at most: someone already
approached does not ask for another, and is not approached again. Approaches are
never declined.

So a Dusk's Conversations can all run at once. In each, the asker speaks first,
then the two take turns, for at most four messages; either may end it sooner.
Everyone sees that the two met, but not who asked whom.
"""

from collections.abc import Mapping, Sequence
from random import Random

from mm.engine.decisions import DuskIntent
from mm.engine.rules import named

PARTNERS_NAMED_AT_MOST = 3
MESSAGES_PER_CONVERSATION = 4

Pair = tuple[str, str]
"""A Conversation's two Residents: the asker, then the one approached."""


def settled(intent: DuskIntent, options: Sequence[str]) -> DuskIntent:
    """An intent as the town carries it out.

    Partners are filtered to the options, each once, at most three, rather than
    rejected. Only askers keep partners, and wanting to talk to nobody is wandering.
    """
    partners = list(named(intent.partners, options)[:PARTNERS_NAMED_AT_MOST])
    if intent.activity != "talk":
        return intent.model_copy(update={"partners": []})
    if not partners:
        return intent.model_copy(update={"activity": "wander", "partners": []})
    return intent.model_copy(update={"partners": partners})


def pair_up(wanted: Mapping[str, Sequence[str]], rng: Random) -> list[Pair]:
    """Every Conversation of the Dusk, from each asker's partners, most wanted first: one
    each at most, so an asker already approached does not ask, and nobody already paired is
    approached."""
    askers = list(wanted)
    rng.shuffle(askers)
    paired: set[str] = set()
    pairs: list[Pair] = []
    for asker in askers:
        partner = next((one for one in wanted[asker] if one not in paired), None)
        if asker in paired or partner is None:
            continue
        pairs.append((asker, partner))
        paired |= {asker, partner}
    return pairs


def next_speaker(pair: Pair, said: int, ended: bool) -> str | None:
    """Who speaks next after `said` messages: the asker first, then turn about; None once over."""
    if ended or said >= MESSAGES_PER_CONVERSATION:
        return None
    return pair[said % 2]


def partner_of(pair: Pair, resident: str) -> str:
    """The other Resident in the Conversation."""
    return pair[1] if resident == pair[0] else pair[0]


def as_seen(pair: Pair, living: Sequence[str]) -> tuple[str, str]:
    """The pair as everyone sees them meet: in seat order, which hides who asked whom."""
    first, second = (name for name in living if name in pair)
    return first, second
