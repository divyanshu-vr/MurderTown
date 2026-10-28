"""Seam 1: Dusk. Who talks to whom, in what order, and who hears what was said."""

import asyncio
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass

from mm.agents import Brain
from mm.engine import GameConfig, Resident
from mm.engine.decisions import (
    Answer,
    ConversationMessage,
    DecisionKind,
    DecisionRequest,
    DuskIntent,
)
from mm.engine.events import ConversationMessagePosted, ConversationStarted, DuskIntentChosen, Event
from mm.engine.perception import perceived_by
from mm.engine.state import GameState
from mm.orchestrator import play_game
from tests.support import (
    Asked,
    Puppet,
    Requests,
    name_at_seat,
    payloads,
    puppets,
    seat_of,
    wrapped,
)

CONFIG = GameConfig(residents=8, murderers=2, max_days=1, seed=4, open_floor_seconds=None)


def chatty(request: DecisionRequest, known: GameState) -> ConversationMessage:
    return ConversationMessage(text=f"{request.resident} speaking.", end_conversation=False)


def seats_met(events: list[Event]) -> list[set[int]]:
    seats = seat_of(GameState.fold(events))
    return [{seats[name] for name in p.pair} for p in payloads(events, ConversationStarted)]


async def test_a_resident_is_approached_for_at_most_two_conversations() -> None:
    talks = {1: {0: [5], 1: [5], 2: [5, 6]}}

    result = await play_game(CONFIG, puppets(talks=talks, messages=chatty))

    met = seats_met(result.events)
    assert sum(5 in pair for pair in met) == 2
    assert all(pair in ({0, 5}, {1, 5}, {2, 5}, {2, 6}) for pair in met)


async def test_the_asker_speaks_first_then_they_take_turns_for_at_most_four_messages() -> None:
    result = await play_game(CONFIG, puppets(talks={1: {0: [1]}}, messages=chatty))

    messages = payloads(result.events, ConversationMessagePosted)
    asker, asked = name_at_seat(result.events, 0), name_at_seat(result.events, 1)
    assert [m.speaker for m in messages] == [asker, asked, asker, asked]


async def test_either_resident_may_end_the_conversation_early() -> None:
    def asked_ends_it(request: DecisionRequest, known: GameState) -> ConversationMessage:
        ending = seat_of(known)[request.resident] == 1
        return ConversationMessage(text="Enough.", end_conversation=ending)

    result = await play_game(CONFIG, puppets(talks={1: {0: [1]}}, messages=asked_ends_it))

    messages = payloads(result.events, ConversationMessagePosted)
    assert [m.ends_conversation for m in messages] == [False, True]


@dataclass(frozen=True)
class NamesStrangers(Puppet):
    """Wants to talk, but only to people who are not there, or to themselves."""

    async def decide(self, request: DecisionRequest, view: Sequence[Event]) -> Answer:
        if request.kind is DecisionKind.DUSK_INTENT:
            partners = ["Nobody", request.resident]
            return Answer(DuskIntent(activity="talk", partners=partners, topic="ghosts"))
        return await super().decide(request, view)


async def test_wanting_to_talk_only_to_strangers_means_wandering() -> None:
    result = await play_game(CONFIG, lambda _: NamesStrangers())

    intents = payloads(result.events, DuskIntentChosen)
    assert {(i.activity, i.partners) for i in intents} == {("wander", ())}
    assert payloads(result.events, ConversationStarted) == []


async def test_who_met_is_public_but_what_they_said_reaches_only_the_pair() -> None:
    result = await play_game(CONFIG, puppets(talks={1: {0: [1]}}, messages=chatty))

    for event in result.events:
        match event.payload:
            case DuskIntentChosen(resident=resident):
                assert event.visibility.residents == (resident,)
            case ConversationStarted():
                assert event.visibility.scope == "everyone"
            case ConversationMessagePosted(speaker=speaker, partner=partner):
                assert set(event.visibility.residents) == {speaker, partner}


class ReverseSeatOrder:
    """Answers later the earlier its Resident's seat, so answers arrive out of order."""

    def __init__(self, inner: Brain, seat: int) -> None:
        self.inner, self.seat = inner, seat

    async def decide(self, request: DecisionRequest, view: Sequence[Event]) -> Answer:
        for _ in range(10 - self.seat):
            await asyncio.sleep(0)
        return await self.inner.decide(request, view)


async def test_conversations_held_at_once_log_the_same_however_fast_each_answers() -> None:
    def zero_ends_at_once(request: DecisionRequest, known: GameState) -> ConversationMessage:
        ending = seat_of(known)[request.resident] == 0
        return ConversationMessage(text="Hm.", end_conversation=ending)

    scripted = puppets(talks={1: {0: [1], 2: [3]}}, messages=zero_ends_at_once)

    def slow(resident: Resident) -> Brain:
        return ReverseSeatOrder(scripted(resident), max(resident.seat, 0))

    instant = await play_game(CONFIG, scripted)
    reversed_answers = await play_game(CONFIG, slow)

    assert [e.model_dump() for e in reversed_answers.events] == [
        e.model_dump() for e in instant.events
    ]
    messages = payloads(instant.events, ConversationMessagePosted)
    conversations = [frozenset((m.speaker, m.partner)) for m in messages]
    assert Counter(conversations).most_common(1)[0][1] == 4  # one capped
    assert min(Counter(conversations).values()) == 1  # one ended at once
    starts = [i for i, c in enumerate(conversations) if i == 0 or c != conversations[i - 1]]
    assert len(starts) == 2  # each Conversation's messages are together


async def test_every_view_is_the_start_of_what_the_resident_perceives_in_the_final_log() -> None:
    asked: Requests = []
    scripted = puppets(talks={1: {0: [1], 2: [3]}}, messages=chatty)

    result = await play_game(CONFIG, wrapped(scripted, lambda brain: Asked(brain, asked)))

    for request, view in asked:
        final = [event.payload for event in perceived_by(result.events, request.resident)]
        assert [event.payload for event in view] == final[: len(view)]
    assert any(request.kind is DecisionKind.CONVERSATION_MESSAGE for request, _ in asked)
