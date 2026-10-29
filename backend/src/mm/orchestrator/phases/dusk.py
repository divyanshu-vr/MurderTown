"""Dusk: the town disperses. Residents wander, do chores, or meet in pairs to talk privately.

Every living Resident says what they mean to do. The askers are paired, and all
the Conversations run at once: each round asks the next speaker of every
unfinished Conversation together. The log holds them Conversation by
Conversation, so it is the same however fast anyone answers. At the end of each
round, a message is appended once its own Conversation's earlier messages and
every earlier Conversation's are: the first Conversation's round by round, each
later one's once the one before is over. So Spectators can watch each as it
goes. Who met is public as soon as they start; what they said reaches only the
pair.
"""

from typing import TYPE_CHECKING, NamedTuple

from mm.engine import Phase
from mm.engine.decisions import ConversationMessage, DecisionKind, DecisionRequest, DuskIntent
from mm.engine.dusk import Pair, as_seen, next_speaker, pair_up, partner_of, settled
from mm.engine.events import ConversationMessagePosted, ConversationStarted, DuskIntentChosen
from mm.engine.rules import trimmed

if TYPE_CHECKING:
    from mm.orchestrator.game import Decided, Game


class Spoken(NamedTuple):
    """A message said at Dusk, with the decision that caused it."""

    message: ConversationMessagePosted
    cause: "Decided[ConversationMessage]"


async def run_dusk(game: "Game") -> None:
    await game.start_phase(Phase.DUSK)
    requests = [
        DecisionRequest(DecisionKind.DUSK_INTENT, name, game.state.others_living(name))
        for name in game.state.living
    ]
    wanted: dict[str, list[str]] = {}
    for chosen in await game.decide_all(requests, DuskIntent):
        intent = settled(chosen.decision, chosen.request.options)
        resident = chosen.request.resident
        if intent.activity == "talk":
            wanted[resident] = intent.partners
        told = DuskIntentChosen(
            resident=resident,
            activity=intent.activity,
            partners=tuple(intent.partners),
            topic=intent.topic,
        )
        await game.append(told, cause=chosen)
    await _talk(game, pair_up(wanted, game.rng))


async def _talk(game: "Game", pairs: list[Pair]) -> None:
    """Run every Conversation together, appending what was said once each round ends."""
    for pair in pairs:
        await game.append(ConversationStarted(residents=as_seen(pair, game.state.living)))

    said: dict[Pair, list[Spoken]] = {pair: [] for pair in pairs}
    logged = 0  # how many messages, in the log's order, are in the log
    while speaking := _speakers(said):
        requests = [
            DecisionRequest(
                DecisionKind.CONVERSATION_MESSAGE, speaker, (partner_of(pair, speaker),)
            )
            for pair, speaker in speaking
        ]
        pending = [spoken.message for spoken in _in_log_order(said)[logged:]]
        answers = await game.decide_all(requests, ConversationMessage, pending)
        for (pair, speaker), answer in zip(speaking, answers, strict=True):
            message = ConversationMessagePosted(
                speaker=speaker,
                partner=partner_of(pair, speaker),
                text=trimmed(answer.decision.text),
                ends_conversation=answer.decision.end_conversation,
            )
            said[pair].append(Spoken(message, answer))
        loggable = _loggable(said)
        for spoken in _in_log_order(said)[logged:loggable]:
            await game.append(spoken.message, cause=spoken.cause)
        logged = loggable


def _in_log_order(said: dict[Pair, list[Spoken]]) -> list[Spoken]:
    """Every message said, Conversation by Conversation, as the log holds them."""
    return [spoken for so_far in said.values() for spoken in so_far]


def _loggable(said: dict[Pair, list[Spoken]]) -> int:
    """How many of the messages, in the log's order, may be logged by now: every
    Conversation's, up to and including the first still going."""
    count = 0
    for pair, so_far in said.items():
        count += len(so_far)
        if _speaks_next(pair, so_far):
            break
    return count


def _speakers(said: dict[Pair, list[Spoken]]) -> list[tuple[Pair, str]]:
    """The next speaker of every Conversation that is still going, in pairing order."""
    return [
        (pair, speaker) for pair, so_far in said.items() if (speaker := _speaks_next(pair, so_far))
    ]


def _speaks_next(pair: Pair, so_far: list[Spoken]) -> str | None:
    """Who speaks next in the Conversation, given what was said so far; None once it is over."""
    ended = bool(so_far) and so_far[-1].message.ends_conversation
    return next_speaker(pair, len(so_far), ended)
