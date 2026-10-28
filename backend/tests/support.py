"""Helpers shared by the seam-1 tests: reading an event log the way a test needs to."""

import asyncio
import json
import re
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from itertools import count
from random import Random
from typing import Any

from mm.agents import Brain, BrainFactory, CallRecorder, ModelCall, llm_agents
from mm.agents.scripted import ScriptedBot
from mm.api.live_games import BrainsFor
from mm.engine import GameConfig, PlayedBy, Resident, Role
from mm.engine.casting import seated_roles
from mm.engine.decisions import (
    SKIP,
    Answer,
    Bid,
    ConversationMessage,
    DecisionKind,
    DecisionRequest,
    DuskIntent,
    Showdown,
    Statement,
    Target,
)
from mm.engine.events import Event, Payload
from mm.engine.state import GameState
from mm.llm import ModelReply, ModelRequest, Usage
from mm.orchestrator import play_game


def payloads[P: Payload](
    events: Sequence[Event], kind: type[P], *, day: int | None = None
) -> list[P]:
    """Every payload of one type, optionally only from one Day."""
    return [
        event.payload
        for event in events
        if isinstance(event.payload, kind) and (day is None or event.day == day)
    ]


def state_before(events: Sequence[Event], first: Callable[[Event], bool]) -> GameState:
    """The true state just before the first event matching a condition."""
    stop = next(index for index, event in enumerate(events) if first(event))
    return GameState.fold(events[:stop])


Script = Mapping[int, Mapping[int, int | None]]
"""Ballots by Day, then by voter seat: the target's seat, or None for SKIP."""

BidRule = Callable[[str, GameState], int]
"""How urgently a Resident bids, given their name and what they know."""

StatementRule = Callable[[DecisionRequest, GameState], Statement]
"""What a Resident says, given the request and what they know."""

MessageRule = Callable[[DecisionRequest, GameState], ConversationMessage]
"""What a Resident says in a Conversation, given the request and what they know."""

Talks = Mapping[int, Mapping[int, Sequence[int]]]
"""Who wants to talk at Dusk, by Day: each asker's seat, then their partners' seats."""


def quiet(name: str, known: GameState) -> int:
    return 0


def keen(name: str, known: GameState) -> int:
    """Every Resident always wants to speak, so only a cap or the clock ends the Open floor."""
    return 2


def ticking(seconds_per_look: float) -> Callable[[], float]:
    """A clock that finds this many more seconds gone each time it is read."""
    looks = count(start=0, step=seconds_per_look)
    return lambda: next(looks)


@dataclass(frozen=True)
class Puppet:
    """A test decision source that does exactly what a test scripts.

    By default it bids 0, holds fire, votes to skip and wanders at Dusk. Unscripted
    Statements, last words, reflections, Night choices and Conversation messages
    come from a scripted bot that never lapses, so unscripted Murderers still kill.
    """

    ballots: Script = field(default_factory=dict)
    bids: BidRule = quiet
    shots: Mapping[int, int] = field(default_factory=dict)
    """For the Sheriff: the seat to fire at, by Day."""
    says: StatementRule | None = None
    kills: Mapping[int, int] = field(default_factory=dict)
    """For the Murderers: the seat to kill on each Day's Night."""
    protects: Mapping[int, int] = field(default_factory=dict)
    """For the Doctor: the seat to protect on each Day's Night."""
    investigations: Mapping[int, int] = field(default_factory=dict)
    """For the Detective: the seat to investigate on each Day's Night."""
    talks: Talks = field(default_factory=dict)
    """Who asks whom for a Conversation at Dusk; everyone else wanders."""
    messages: MessageRule | None = None
    """What Residents say in a Conversation, if not left to a scripted bot."""

    async def decide(self, request: DecisionRequest, view: Sequence[Event]) -> Answer:
        known = GameState.fold(view)
        me = request.resident
        match request.kind:
            case DecisionKind.BALLOT:
                target = self.ballots.get(known.day, {}).get(seat_of(known)[me])
                choice = SKIP if target is None else known.residents[target].name
                return Answer(Target(target=choice, reason="scripted"))
            case DecisionKind.BID:
                return Answer(Bid(urgency=self.bids(me, known), reason="scripted"))
            case DecisionKind.SHOWDOWN:
                seat = self.shots.get(known.day)
                if seat is None:
                    return Answer(Showdown(fire=False, target=None, reason="scripted"))
                target = known.residents[seat].name
                return Answer(Showdown(fire=True, target=target, reason="scripted"))
            case DecisionKind.STATEMENT if self.says:
                return Answer(self.says(request, known))
            case DecisionKind.DUSK_INTENT:
                seats = self.talks.get(known.day, {}).get(seat_of(known)[me], ())
                partners = [known.residents[seat].name for seat in seats]
                activity = "talk" if partners else "wander"
                return Answer(DuskIntent(activity=activity, partners=partners, topic="scripted"))
            case DecisionKind.CONVERSATION_MESSAGE if self.messages:
                return Answer(self.messages(request, known))
            case DecisionKind.KILL_VOTE | DecisionKind.PROTECT | DecisionKind.INVESTIGATE if (
                seat := self._chosen_at_night(request.kind, known.day)
            ) is not None:
                return Answer(Target(target=known.residents[seat].name, reason="scripted"))
            case _:
                return await ScriptedBot(Random(me), lapses=False).decide(request, view)

    def _chosen_at_night(self, kind: DecisionKind, day: int) -> int | None:
        scripted = {
            DecisionKind.KILL_VOTE: self.kills,
            DecisionKind.PROTECT: self.protects,
            DecisionKind.INVESTIGATE: self.investigations,
        }
        return scripted[kind].get(day)


def may_perceive(event: Event, resident: str) -> bool:
    """The visibility rule, restated independently of the code under test."""
    scope = event.visibility.scope
    return scope == "everyone" or (scope == "residents" and resident in event.visibility.residents)


def seat_of(state: GameState) -> dict[str, int]:
    return {resident.name: resident.seat for resident in state.residents}


def everyone_votes_for(target: int, seats: range = range(6)) -> dict[int, int | None]:
    """Ballots by seat, all for `target`, who abstains: nobody may vote for themselves."""
    return {seat: target for seat in seats if seat != target}


Requests = list[tuple[DecisionRequest, list[Event]]]
"""Every request a game made, each with the view it came with."""


class Asked:
    """A decision source that passes every request on, noting it with the view it came with."""

    def __init__(self, inner: Brain, asked: Requests) -> None:
        self.inner, self.asked = inner, asked

    async def decide(self, request: DecisionRequest, view: Sequence[Event]) -> Answer:
        self.asked.append((request, list(view)))
        return await self.inner.decide(request, view)


class Delayed:
    """A decision source that lets the event loop run `turns()` times before each answer,
    so answers given at once can arrive in any order."""

    def __init__(self, inner: Brain, turns: Callable[[], int]) -> None:
        self.inner, self.turns = inner, turns

    async def decide(self, request: DecisionRequest, view: Sequence[Event]) -> Answer:
        for _ in range(self.turns()):
            await asyncio.sleep(0)
        return await self.inner.decide(request, view)


def wrapped(factory: BrainFactory, wrap: Callable[[Brain], Brain]) -> BrainFactory:
    """Every Resident's decision source from `factory`, passed through `wrap`."""

    def make(resident: Resident) -> Brain:
        return wrap(factory(resident))

    return make


def puppets(
    ballots: Script | None = None,
    *,
    bids: BidRule = quiet,
    shots: Mapping[int, int] | None = None,
    says: StatementRule | None = None,
    kills: Mapping[int, int] | None = None,
    protects: Mapping[int, int] | None = None,
    investigations: Mapping[int, int] | None = None,
    talks: Talks | None = None,
    messages: MessageRule | None = None,
) -> BrainFactory:
    puppet = Puppet(
        ballots=ballots or {},
        bids=bids,
        shots=shots or {},
        says=says,
        kills=kills or {},
        protects=protects or {},
        investigations=investigations or {},
        talks=talks or {},
        messages=messages,
    )

    def make(resident: Resident) -> Brain:
        return puppet

    return make


def name_at_seat(events: Sequence[Event], seat: int) -> str:
    return GameState.fold(events).residents[seat].name


def seats_by_role(config: GameConfig) -> dict[Role, list[int]]:
    """Which seats hold which role for this config, in seat order."""
    seats: dict[Role, list[int]] = {}
    for seat, role in sorted(seated_roles(config).items()):
        seats.setdefault(role, []).append(seat)
    return seats


def own_role(request: ModelRequest) -> str:
    """The Agent's true role, as its system briefing states it."""
    found = re.search(r"You are (?:secretly )?(?:a|the) (\w+)", request.system)
    assert found, "every briefing states the Agent's role"
    return found.group(1).lower()


KIND_BY_FIELD = {
    "my_role": DecisionKind.STATEMENT,
    "urgency": DecisionKind.BID,
    "fire": DecisionKind.SHOWDOWN,
    "journal_entry": DecisionKind.REFLECTION,
    "proposed_victim": DecisionKind.DEN_MESSAGE,
    "activity": DecisionKind.DUSK_INTENT,
    "end_conversation": DecisionKind.CONVERSATION_MESSAGE,
}

KIND_BY_WORDING = {
    "the Vote is open": DecisionKind.BALLOT,
    "Choose tonight's Victim": DecisionKind.KILL_VOTE,
    "Choose one Resident to protect": DecisionKind.PROTECT,
    "Choose one Resident to investigate": DecisionKind.INVESTIGATE,
}


def answer_kind(request: ModelRequest) -> DecisionKind:
    """Which decision a model request is for.

    Providers are told nothing about the game, so a test fake works it out: from a
    field only that kind's answer has, or, where answers share a shape, from the
    wording of the instructions.
    """
    fields = set(request.schema["properties"])
    for only_in, kind in KIND_BY_FIELD.items():
        if only_in in fields:
            return kind
    if "target" in fields:
        return next(kind for words, kind in KIND_BY_WORDING.items() if words in request.prompt)
    narrating = request.system.startswith("You are the narrator")
    return DecisionKind.RECAP if narrating else DecisionKind.LAST_WORDS


def listed_options(prompt: str) -> list[str]:
    """The options a ballot prompt lists, in the order it lists them."""
    found = re.search(r"spelled as shown\): (.+)", prompt)
    assert found, "a ballot prompt lists its options"
    return found.group(1).split(", ")


def model_answer(data: dict[str, Any]) -> ModelReply:
    usage = Usage(input_tokens=40, output_tokens=12, cache_read_tokens=30)
    return ModelReply(outcome="ok", data=data, text=json.dumps(data), usage=usage, latency_ms=3)


def statement_answer(text: str, request: ModelRequest, **fields: Any) -> dict[str, Any]:
    """A complete Statement answer: the words, the speaker's true role, then any `fields` given."""
    plain = Statement.plain(text).model_dump(mode="json")
    return {**plain, "my_role": own_role(request), **fields}


def sensible_answer(request: ModelRequest) -> ModelReply:  # noqa: C901 - one answer per kind
    """A cooperative model: short Statements, quiet bids, held fire, SKIP, brief notes,
    and at Night the first option it is offered."""
    match answer_kind(request):
        case DecisionKind.STATEMENT:
            return model_answer(statement_answer("I am watching every one of you.", request))
        case DecisionKind.BID:
            return model_answer({"urgency": 0, "reason": "listening"})
        case DecisionKind.SHOWDOWN:
            return model_answer({"fire": False, "target": None, "reason": "not yet"})
        case DecisionKind.BALLOT:
            return model_answer({"target": "SKIP", "reason": "not sure yet"})
        case DecisionKind.LAST_WORDS:
            return model_answer({"text": "You will regret this."})
        case DecisionKind.REFLECTION:
            return model_answer({"journal_entry": "Quiet so far.", "notebook": "Stay alert.",
                                 "suspicions": []})  # fmt: skip
        case DecisionKind.DEN_MESSAGE:
            return model_answer({"text": "Careful tonight.", "proposed_victim": None})
        case DecisionKind.KILL_VOTE | DecisionKind.PROTECT | DecisionKind.INVESTIGATE:
            return model_answer({"target": listed_options(request.prompt)[0], "reason": "a hunch"})
        case DecisionKind.RECAP:
            return model_answer({"text": "Another Day dawns over the town."})
        case DecisionKind.DUSK_INTENT:
            partner = listed_options(request.prompt)[0]
            return model_answer({"activity": "talk", "partners": [partner], "topic": "the vote"})
        case DecisionKind.CONVERSATION_MESSAGE:  # a reply ends it, so Conversations have two
            replying = "(to " in request.prompt
            return model_answer({"text": "Let us keep an eye on each other.",
                                 "end_conversation": replying})  # fmt: skip


async def played_by(model: "FakeModel", config: GameConfig) -> tuple[list[Event], list[ModelCall]]:
    """A whole game played by Agents on a fake model: its log and every model call recorded."""
    calls: list[ModelCall] = []

    async def record(call: ModelCall) -> None:
        calls.append(call)

    result = await play_game(config, llm_agents(model, PlayedBy(), record, config.seed))
    return result.events, calls


def agents_on(model: "FakeModel") -> BrainsFor:
    """An API decision source: every Resident an Agent on `model`, resuming from its records."""

    def brains_for(
        config: GameConfig, record: CallRecorder, recorded: Sequence[ModelCall]
    ) -> BrainFactory:
        return llm_agents(model, PlayedBy(), record, config.seed, recorded=recorded)

    return brains_for


class FakeModel:
    """A test model provider that answers from a script and remembers every request."""

    def __init__(
        self, respond: Callable[[ModelRequest], ModelReply] = sensible_answer, name: str = "fake"
    ) -> None:
        self.respond, self.name = respond, name
        self.requests: list[ModelRequest] = []

    async def complete(self, request: ModelRequest) -> ModelReply:
        self.requests.append(request)
        return self.respond(request)
