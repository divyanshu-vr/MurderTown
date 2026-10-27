"""Helpers shared by the seam-1 tests: reading an event log the way a test needs to."""

from collections.abc import Callable, Mapping, Sequence

from mm.agents import Brain, BrainFactory
from mm.engine import GameConfig, Resident, Role
from mm.engine.decisions import SKIP, Ballot, Decision, DecisionKind, DecisionRequest, Statement
from mm.engine.events import Event, Payload, RoleAssigned
from mm.engine.state import GameState
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


class Puppet:
    """A test decision source that votes exactly as scripted and otherwise SKIPs."""

    def __init__(self, ballots: Script) -> None:
        self.ballots = ballots

    async def decide(self, request: DecisionRequest, view: Sequence[Event]) -> Decision:
        known = GameState.fold(view)
        if request.kind is DecisionKind.BALLOT:
            target = self.ballots.get(known.day, {}).get(seat_of(known)[request.resident])
            return Ballot(choice=SKIP if target is None else known.residents[target].name)
        return Statement(text="I have nothing to add.")


def seat_of(state: GameState) -> dict[str, int]:
    return {resident.name: resident.seat for resident in state.residents}


def wrapped(factory: BrainFactory, wrap: Callable[[Brain], Brain]) -> BrainFactory:
    """Every Resident's decision source from `factory`, passed through `wrap`."""

    def make(resident: Resident) -> Brain:
        return wrap(factory(resident))

    return make


def puppets(ballots: Script | None = None) -> BrainFactory:
    def make(resident: Resident) -> Brain:
        return Puppet(ballots or {})

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
