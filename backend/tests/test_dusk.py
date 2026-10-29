"""Seam 1: Dusk. Who talks to whom, in what order, and who hears what was said."""

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
    Delayed,
    Puppet,
    Requests,
    everyone_alive_on_day_two,
    name_at_seat,
    payloads,
    puppets,
    seat_of,
    wrapped,
)

CONFIG = GameConfig(residents=8, murderers=2, max_days=2, seed=4, open_floor_seconds=None)
"""The first Night's Victim is saved, so all eight meet at the first Dusk, Day 2's."""


def chatty(request: DecisionRequest, known: GameState) -> ConversationMessage:
    return ConversationMessage(text=f"{request.resident} speaking.", end_conversation=False)


def seats_met(events: list[Event]) -> list[set[int]]:
    seats = seat_of(GameState.fold(events))
    return [{seats[name] for name in p.residents} for p in payloads(events, ConversationStarted)]


async def test_a_resident_is_in_at_most_one_conversation_a_dusk() -> None:
    talks = {2: {0: [5], 1: [5], 2: [5, 6]}}

    result = await play_game(
        CONFIG, puppets(talks=talks, messages=chatty, **everyone_alive_on_day_two(CONFIG))
    )

    met = seats_met(result.events)
    assert sum(5 in pair for pair in met) == 1
    assert all(pair in ({0, 5}, {1, 5}, {2, 5}, {2, 6}) for pair in met)
    assert max(Counter(seat for pair in met for seat in pair).values()) == 1


async def test_the_asker_speaks_first_then_they_take_turns_for_at_most_four_messages() -> None:
    result = await play_game(
        CONFIG, puppets(talks={2: {0: [1]}}, messages=chatty, **everyone_alive_on_day_two(CONFIG))
    )

    messages = payloads(result.events, ConversationMessagePosted)
    asker, asked = name_at_seat(result.events, 0), name_at_seat(result.events, 1)
    assert [m.speaker for m in messages] == [asker, asked, asker, asked]


async def test_either_resident_may_end_the_conversation_early() -> None:
    def asked_ends_it(request: DecisionRequest, known: GameState) -> ConversationMessage:
        ending = seat_of(known)[request.resident] == 1
        return ConversationMessage(text="Enough.", end_conversation=ending)

    scripted = puppets(
        talks={2: {0: [1]}}, messages=asked_ends_it, **everyone_alive_on_day_two(CONFIG)
    )

    result = await play_game(CONFIG, scripted)

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
    result = await play_game(
        CONFIG, puppets(talks={2: {0: [1]}}, messages=chatty, **everyone_alive_on_day_two(CONFIG))
    )

    assert payloads(result.events, ConversationMessagePosted)
    for event in result.events:
        match event.payload:
            case DuskIntentChosen(resident=resident):
                assert event.visibility.residents == (resident,)
            case ConversationStarted():
                assert event.visibility.scope == "everyone"
            case ConversationMessagePosted(speaker=speaker, partner=partner):
                assert set(event.visibility.residents) == {speaker, partner}


async def test_conversations_held_at_once_log_the_same_however_fast_each_answers() -> None:
    def zero_ends_at_once(request: DecisionRequest, known: GameState) -> ConversationMessage:
        ending = seat_of(known)[request.resident] == 0
        return ConversationMessage(text="Hm.", end_conversation=ending)

    scripted = puppets(
        talks={2: {0: [1], 2: [3]}}, messages=zero_ends_at_once, **everyone_alive_on_day_two(CONFIG)
    )

    def slow(resident: Resident) -> Brain:  # the lower the seat, the later the answer
        return Delayed(scripted(resident), lambda: 10 - max(resident.seat, 0))

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


async def test_each_conversation_is_logged_as_it_is_said_once_every_earlier_one_is_over() -> None:
    asked: Requests = []
    logged_after: list[int] = []  # for each message logged, how many had been asked for

    async def noted(event: Event) -> None:
        if isinstance(event.payload, ConversationMessagePosted):
            kinds = [request.kind for request, _ in asked]
            logged_after.append(kinds.count(DecisionKind.CONVERSATION_MESSAGE))

    scripted = puppets(
        talks={2: {0: [1], 2: [3]}}, messages=chatty, **everyone_alive_on_day_two(CONFIG)
    )
    await play_game(CONFIG, wrapped(scripted, lambda brain: Asked(brain, asked)), observers=[noted])

    # each round asks both Conversations, then logs the first's message; the second's follow it
    assert logged_after == [2, 4, 6, 8, 8, 8, 8, 8]


async def test_every_view_is_the_start_of_what_the_resident_perceives_in_the_final_log() -> None:
    asked: Requests = []
    scripted = puppets(
        talks={2: {0: [1], 2: [3]}}, messages=chatty, **everyone_alive_on_day_two(CONFIG)
    )

    result = await play_game(CONFIG, wrapped(scripted, lambda brain: Asked(brain, asked)))

    for request, view in asked:
        final = [event.payload for event in perceived_by(result.events, request.resident)]
        assert [event.payload for event in view] == final[: len(view)]
    assert any(request.kind is DecisionKind.CONVERSATION_MESSAGE for request, _ in asked)
