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
            seat_of = {resident.name: resident.seat for resident in known.residents}
            name_at = {resident.seat: resident.name for resident in known.residents}
            target = self.ballots.get(known.day, {}).get(seat_of[request.resident])
            return Ballot(choice=SKIP if target is None else name_at[target])
        return Statement(text="I have nothing to add.")


def puppets(ballots: Script | None = None) -> BrainFactory:
    def make(resident: Resident) -> Brain:
        return Puppet(ballots or {})

    return make


def name_at_seat(events: Sequence[Event], seat: int) -> str:
    return GameState.fold(events).residents[seat].name


async def seats_by_role(config: GameConfig) -> dict[Role, list[int]]:
    """Which seats hold which role for this config. Casting is deterministic, so a dry run tells."""
    events = (await play_game(config.model_copy(update={"max_days": 1}), puppets())).events
    seat_of = {resident.name: resident.seat for resident in GameState.fold(events).residents}
    seats: dict[Role, list[int]] = {}
    for assignment in payloads(events, RoleAssigned):
        seats.setdefault(assignment.role, []).append(seat_of[assignment.resident])
    return {role: sorted(found) for role, found in seats.items()}
