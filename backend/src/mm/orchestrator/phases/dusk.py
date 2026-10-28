"""Dusk: the town disperses. Residents wander, do chores, or meet in pairs to talk privately.

Every living Resident says what they mean to do. The askers are paired, and the
pairs talk in waves of Conversations that run at once. Within a wave, each
round asks the next speaker of every unfinished Conversation together. What
they say is held back until the wave ends, then appended Conversation by
Conversation, so the log is the same however fast anyone answers. Who met is
public as soon as a wave begins; what they said reaches only the pair.
"""

from typing import TYPE_CHECKING, NamedTuple

from mm.engine import Phase
from mm.engine.decisions import ConversationMessage, DecisionKind, DecisionRequest, DuskIntent
from mm.engine.dusk import Pair, as_seen, next_speaker, pair_up, partner_of, settled, waves
from mm.engine.events import ConversationMessagePosted, ConversationStarted, DuskIntentChosen
from mm.engine.rules import trimmed

if TYPE_CHECKING:
    from mm.orchestrator.game import Decided, Game


class Spoken(NamedTuple):
    """A message said in a wave but not appended yet, with the decision that caused it."""

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
    for wave in waves(pair_up(wanted, game.rng)):
        await _talk(game, wave)


async def _talk(game: "Game", wave: list[Pair]) -> None:
    """Run one wave of Conversations together, then append what was said."""
    for pair in wave:
        await game.append(ConversationStarted(residents=as_seen(pair, game.state.living)))

    said: dict[Pair, list[Spoken]] = {pair: [] for pair in wave}
    while speaking := _speakers(said):
        requests = [
            DecisionRequest(
                DecisionKind.CONVERSATION_MESSAGE, speaker, (partner_of(pair, speaker),)
            )
            for pair, speaker in speaking
        ]
        pending = [spoken.message for spoken_so_far in said.values() for spoken in spoken_so_far]
        answers = await game.decide_all(requests, ConversationMessage, pending)
        for (pair, speaker), answer in zip(speaking, answers, strict=True):
            message = ConversationMessagePosted(
                speaker=speaker,
                partner=partner_of(pair, speaker),
                text=trimmed(answer.decision.text),
                ends_conversation=answer.decision.end_conversation,
            )
            said[pair].append(Spoken(message, answer))

    for spoken_so_far in said.values():
        for spoken in spoken_so_far:
            await game.append(spoken.message, cause=spoken.cause)


def _speakers(said: dict[Pair, list[Spoken]]) -> list[tuple[Pair, str]]:
    """The next speaker of every Conversation that is still going, in wave order."""
    speaking = []
    for pair, spoken in said.items():
        ended = bool(spoken) and spoken[-1].message.ends_conversation
        if speaker := next_speaker(pair, len(spoken), ended):
            speaking.append((pair, speaker))
    return speaking
