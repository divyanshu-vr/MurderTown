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
    AttackThwarted,
    BallotCast,
    BidPlaced,
    DecisionFellBack,
    DenMessagePosted,
    Event,
    EventPayload,
    GameEnded,
    GameStarted,
    KillVoteCast,
    LastWordsSpoken,
    PhaseStarted,
    RecapNarrated,
    ReflectionWritten,
    ResidentDied,
    ResidentInvestigated,
    ResidentProtected,
    RoleAssigned,
    SheriffFired,
    SheriffHeldFire,
    StatementMade,
    VictimChosen,
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
    victims: dict[int, str] = field(default_factory=dict)
    """The Den's Victim on each Night, by Day."""
    protections: dict[int, str] = field(default_factory=dict)
    """Whom the Doctor protected on each Night, by Day."""
    investigated: set[str] = field(default_factory=set)
    winner: Side | None = None

    @classmethod
    def fold(cls, events: Iterable[Event]) -> "GameState":
        state = cls()
        for event in events:
            state.apply(event.payload)
        return state

    def apply(self, payload: EventPayload) -> None:  # noqa: C901 - one case per event type
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
            case VictimChosen(victim=victim):
                self.victims[self.day] = victim
            case ResidentProtected(target=target):
                self.protections[self.day] = target
            case ResidentInvestigated(target=target):
                self.investigated.add(target)
            case GameEnded(winner=winner):
                self.winner, self.phase = winner, Phase.ENDED
            case (
                BidPlaced() | StatementMade() | BallotCast() | VoteResolved() | LastWordsSpoken()
                | SheriffHeldFire() | ReflectionWritten() | DecisionFellBack() | DenMessagePosted()
                | KillVoteCast() | AttackThwarted() | RecapNarrated()
            ):  # fmt: skip
                pass  # recorded in the log, but they change nothing the state tracks
            case unknown:
                assert_never(unknown)

    @property
    def living(self) -> list[str]:
        """Names of living Residents, in seat order."""
        return [resident.name for resident in self.residents if resident.name not in self.dead]

    def living_as(self, role: Role) -> list[str]:
        """Names of living Residents with one role, in seat order. Needs the true state."""
        return [name for name in self.living if self.roles.get(name) is role]

    def others_living(self, name: str) -> tuple[str, ...]:
        """Every living Resident except `name`, in seat order."""
        return tuple(other for other in self.living if other != name)
