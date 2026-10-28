"""Rules of Dusk: who talks to whom, in what waves, and who speaks next in a Conversation.

Each Resident who wants to talk names up to three partners, most wanted first.
The askers are taken in a random order, and each gets their first preference who
is still available. A Resident can ask for one Conversation (they make one
intent) and be approached for at most two more. Approaches are never declined.

Conversations run in waves: no Resident is in two Conversations of one wave, so
a wave's Conversations can run at once. In each, the asker speaks first, then the
two take turns, for at most four messages; either may end it sooner. Everyone
sees that the two met, but not who asked whom.
"""

from collections import Counter
from collections.abc import Mapping, Sequence
from random import Random

from mm.engine.decisions import DuskIntent
from mm.engine.rules import named

PARTNERS_NAMED_AT_MOST = 3
APPROACHED_AT_MOST = 2
"""How many Conversations a Resident can be approached for, besides the one they ask for."""
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
    """Every Conversation of the Dusk, from each asker's partners, most wanted first.

    A partner is unavailable once they have been approached twice, or if the two
    are already paired. An asker who has been approached twice can still ask.
    """
    askers = list(wanted)
    rng.shuffle(askers)
    approached: Counter[str] = Counter()
    pairs: list[Pair] = []
    for asker in askers:
        for partner in wanted[asker]:
            already_paired = any({asker, partner} == set(pair) for pair in pairs)
            if approached[partner] < APPROACHED_AT_MOST and not already_paired:
                pairs.append((asker, partner))
                approached[partner] += 1
                break
    return pairs


def waves(pairs: Sequence[Pair]) -> list[list[Pair]]:
    """The pairs, in order, each in the first wave where neither of the two is busy."""
    result: list[list[Pair]] = []
    for pair in pairs:
        free = next((wave for wave in result if not set(pair) & _busy_in(wave)), None)
        if free is None:
            result.append([pair])
        else:
            free.append(pair)
    return result


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


def _busy_in(wave: Sequence[Pair]) -> set[str]:
    """Everyone already in one of the wave's Conversations."""
    return {name for pair in wave for name in pair}
