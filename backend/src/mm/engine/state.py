"""Game state is a fold of events.

Folding the whole log gives the true state of the game. Folding only the events
one Resident may perceive gives exactly what that Resident knows, with the same
code, so the two can never drift apart.
"""

from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import assert_never

from mm.engine.config import GameConfig
from mm.engine.events import (
    BallotCast,
    BidPlaced,
    DecisionFellBack,
    Event,
    EventPayload,
    GameEnded,
    GameStarted,
    LastWordsSpoken,
    PhaseStarted,
    ReflectionWritten,
    ResidentDied,
    RoleAssigned,
    SheriffFired,
    SheriffHeldFire,
    StatementMade,
    VoteResolved,
)
from mm.engine.phases import Phase
from mm.engine.residents import Resident
from mm.engine.roles import Role, Side


@dataclass
class GameState:
    config: GameConfig | None = None
    residents: tuple[Resident, ...] = ()
    roles: dict[str, Role] = field(default_factory=dict)
    dead: set[str] = field(default_factory=set)
    day: int = 0
    phase: Phase = Phase.SETUP
    bullet_spent: bool = False
    winner: Side | None = None

    @classmethod
    def fold(cls, events: Iterable[Event]) -> "GameState":
        state = cls()
        for event in events:
            state.apply(event.payload)
        return state

    def apply(self, payload: EventPayload) -> None:
        match payload:
            case GameStarted(config=config, residents=residents):
                self.config, self.residents = config, residents
            case RoleAssigned(resident=resident, role=role, teammates=teammates):
                self.roles[resident] = role
                self.roles.update(dict.fromkeys(teammates, Role.MURDERER))
            case PhaseStarted(day=day, phase=phase):
                self.day, self.phase = day, phase
            case ResidentDied(resident=resident, role=role):
                self.dead.add(resident)
                self.roles[resident] = role
            case SheriffFired():
                self.bullet_spent = True
            case GameEnded(winner=winner):
                self.winner, self.phase = winner, Phase.ENDED
            case (
                BidPlaced() | StatementMade() | BallotCast() | VoteResolved() | LastWordsSpoken()
                | SheriffHeldFire() | ReflectionWritten() | DecisionFellBack()
            ):  # fmt: skip
                pass  # recorded in the log, but they change nothing the state tracks
            case unknown:
                assert_never(unknown)

    @property
    def living(self) -> list[str]:
        """Names of living Residents, in seat order."""
        return [resident.name for resident in self.residents if resident.name not in self.dead]
