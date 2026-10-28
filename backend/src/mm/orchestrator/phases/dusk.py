"""Dusk: the town disperses. Residents wander, do chores, or meet in pairs to talk privately.

Every living Resident says what they mean to do. The talkers are paired, and
the pairs talk in waves of Conversations that run at once. Within a wave, each
round asks the next speaker of every unfinished Conversation together. What
they say is held back until the wave ends, then appended Conversation by
Conversation, so the log is the same however fast anyone answers. Who met is
public as soon as a wave begins; what they said reaches only the pair.
"""

from typing import TYPE_CHECKING

from mm.engine import Phase
from mm.engine.decisions import ConversationMessage, DecisionKind, DecisionRequest, DuskIntent
from mm.engine.dusk import Pair, next_speaker, pair_up, settled, waves
from mm.engine.events import ConversationMessagePosted, ConversationStarted, DuskIntentChosen
from mm.engine.rules import trimmed

if TYPE_CHECKING:
    from mm.orchestrator.game import Decided, Game


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
        in_seat_order = tuple(name for name in game.state.living if name in pair)
        await game.append(ConversationStarted(pair=(in_seat_order[0], in_seat_order[1])))

    said: dict[Pair, list[tuple[ConversationMessagePosted, Decided[ConversationMessage]]]]
    said = {pair: [] for pair in wave}
    while speaking := _speakers(said):
        requests = [
            DecisionRequest(DecisionKind.CONVERSATION_MESSAGE, speaker, (_other(pair, speaker),))
            for pair, speaker in speaking
        ]
        pending = [message for messages in said.values() for message, _ in messages]
        answers = await game.decide_all(requests, ConversationMessage, pending)
        for (pair, speaker), answer in zip(speaking, answers, strict=True):
            message = ConversationMessagePosted(
                speaker=speaker,
                partner=_other(pair, speaker),
                text=trimmed(answer.decision.text),
                ends_conversation=answer.decision.end_conversation,
            )
            said[pair].append((message, answer))

    for messages in said.values():
        for message, answer in messages:
            await game.append(message, cause=answer)


def _speakers(
    said: dict[Pair, list[tuple[ConversationMessagePosted, "Decided[ConversationMessage]"]]],
) -> list[tuple[Pair, str]]:
    """The next speaker of every Conversation that is still going, in wave order."""
    speaking = []
    for pair, messages in said.items():
        ended = bool(messages) and messages[-1][0].ends_conversation
        if speaker := next_speaker(pair, len(messages), ended):
            speaking.append((pair, speaker))
    return speaking


def _other(pair: Pair, speaker: str) -> str:
    return pair[1] if speaker == pair[0] else pair[0]
