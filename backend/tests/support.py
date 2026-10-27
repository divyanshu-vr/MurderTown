"""Helpers shared by the seam-1 tests: reading an event log the way a test needs to."""

import json
import re
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from random import Random
from typing import Any

from mm.agents import Brain, BrainFactory
from mm.agents.scripted import ScriptedBot
from mm.engine import GameConfig, Resident, Role
from mm.engine.decisions import (
    SKIP,
    Answer,
    Ballot,
    Bid,
    DecisionKind,
    DecisionRequest,
    Showdown,
    Statement,
)
from mm.engine.events import Event, Payload, RoleAssigned
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


def quiet(name: str, known: GameState) -> int:
    return 0


@dataclass(frozen=True)
class Puppet:
    """A test decision source that does exactly what a test scripts.

    By default it bids 0, holds fire and votes to skip. Unscripted Statements,
    last words and reflections come from a scripted bot.
    """

    ballots: Script = field(default_factory=dict)
    bids: BidRule = quiet
    shots: Mapping[int, int] = field(default_factory=dict)
    """For the Sheriff: the seat to fire at, by Day."""
    says: StatementRule | None = None

    async def decide(self, request: DecisionRequest, view: Sequence[Event]) -> Answer:
        known = GameState.fold(view)
        me = request.resident
        match request.kind:
            case DecisionKind.BALLOT:
                target = self.ballots.get(known.day, {}).get(seat_of(known)[me])
                choice = SKIP if target is None else known.residents[target].name
                return Answer(Ballot(choice=choice))
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
            case _:
                return await ScriptedBot(Random(me)).decide(request, view)


def seat_of(state: GameState) -> dict[str, int]:
    return {resident.name: resident.seat for resident in state.residents}


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
) -> BrainFactory:
    puppet = Puppet(ballots=ballots or {}, bids=bids, shots=shots or {}, says=says)

    def make(resident: Resident) -> Brain:
        return puppet

    return make


def name_at_seat(events: Sequence[Event], seat: int) -> str:
    return GameState.fold(events).residents[seat].name


async def seats_by_role(config: GameConfig) -> dict[Role, list[int]]:
    """Which seats hold which role for this config. Casting is deterministic, so a dry run tells."""
    events = (await play_game(config.model_copy(update={"max_days": 1}), puppets())).events
    seats_of_names = seat_of(GameState.fold(events))
    seats: dict[Role, list[int]] = {}
    for assignment in payloads(events, RoleAssigned):
        seats.setdefault(assignment.role, []).append(seats_of_names[assignment.resident])
    return {role: sorted(found) for role, found in seats.items()}


KIND_BY_FIELD = {
    "my_role": DecisionKind.STATEMENT,
    "urgency": DecisionKind.BID,
    "fire": DecisionKind.SHOWDOWN,
    "choice": DecisionKind.BALLOT,
    "journal_entry": DecisionKind.REFLECTION,
}


def answer_kind(request: ModelRequest) -> DecisionKind:
    """Which decision a model request is for, read from the shape of its answer schema."""
    fields = set(request.schema["properties"])
    found = [kind for field, kind in KIND_BY_FIELD.items() if field in fields]
    return found[0] if found else DecisionKind.LAST_WORDS


def own_role(request: ModelRequest) -> str:
    """The Agent's true role, as its system briefing states it."""
    found = re.search(r"You are (?:secretly )?(?:a|the) (\w+)", request.system)
    assert found, "every briefing states the Agent's role"
    return found.group(1).lower()


def listed_options(prompt: str) -> list[str]:
    """The options a ballot prompt lists, in the order it lists them."""
    found = re.search(r"spelled as shown\): (.+)", prompt)
    assert found, "a ballot prompt lists its options"
    return found.group(1).split(", ")


def model_answer(data: dict[str, Any]) -> ModelReply:
    usage = Usage(input_tokens=40, output_tokens=12, cache_read_tokens=30, cache_write_tokens=0)
    return ModelReply(
        outcome="ok", data=data, text=json.dumps(data), usage=usage, latency_ms=3, cost_usd=0.0002
    )


def statement_answer(text: str, request: ModelRequest, **fields: Any) -> dict[str, Any]:
    """A complete Statement answer: the words, the speaker's true role, then any `fields` given."""
    plain = Statement.plain(text).model_dump(mode="json")
    return {**plain, "my_role": own_role(request), **fields}


def sensible_answer(request: ModelRequest) -> ModelReply:
    """A cooperative model: short Statements, quiet bids, held fire, SKIP and brief notes."""
    match answer_kind(request):
        case DecisionKind.STATEMENT:
            return model_answer(statement_answer("I am watching every one of you.", request))
        case DecisionKind.BID:
            return model_answer({"urgency": 0, "reason": "listening"})
        case DecisionKind.SHOWDOWN:
            return model_answer({"fire": False, "target": None, "reason": "not yet"})
        case DecisionKind.BALLOT:
            return model_answer({"choice": "SKIP"})
        case DecisionKind.LAST_WORDS:
            return model_answer({"text": "You will regret this."})
        case DecisionKind.REFLECTION:
            return model_answer({"journal_entry": "Quiet so far.", "notebook": "Stay alert.",
                                 "suspicions": []})  # fmt: skip


class FakeModel:
    """A test model provider that answers from a script and remembers every request."""

    name = "fake"

    def __init__(self, respond: Callable[[ModelRequest], ModelReply] = sensible_answer) -> None:
        self.respond = respond
        self.requests: list[ModelRequest] = []

    async def complete(self, request: ModelRequest) -> ModelReply:
        self.requests.append(request)
        return self.respond(request)
