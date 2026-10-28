"""Hand-made logs: a cast game's opening, then whatever events a test needs, stamped as a game
stamps them, so each rule of the review and the measures can be seen on its own."""

from random import Random

from mm.engine import GameConfig, Phase, Role
from mm.engine.casting import cast
from mm.engine.decisions import Suspicion
from mm.engine.events import (
    BallotCast,
    Event,
    EventPayload,
    GameStarted,
    PhaseStarted,
    ReflectionWritten,
    RoleAssigned,
    StatementMade,
)
from mm.orchestrator.log import EventLog

CONFIG = GameConfig(residents=8, murderers=2, seed=4)
OPENING = cast(CONFIG, Random(CONFIG.seed))


def holding(role: Role) -> list[str]:
    return [p.resident for p in OPENING if isinstance(p, RoleAssigned) and p.role is role]


(M1, M2), (C1, C2, C3) = holding(Role.MURDERER), holding(Role.CIVILIAN)
(DOC,), (DET,), (SHERIFF,) = holding(Role.DOCTOR), holding(Role.DETECTIVE), holding(Role.SHERIFF)
SEATS = {r.name: r.seat for p in OPENING if isinstance(p, GameStarted) for r in p.residents}


async def logged(*later: EventPayload, config: GameConfig = CONFIG) -> list[Event]:
    """The game's opening, then these events, stamped as the game stamps them. Another
    `config` of the same rules and seed casts the same Residents in the same roles."""
    log = EventLog()
    for payload in [*cast(config, Random(config.seed)), *later]:
        await log.append(payload)
    return log.events


def day(number: int, phase: Phase = Phase.DISCUSSION) -> PhaseStarted:
    return PhaseStarted(day=number, phase=phase)


def says(
    speaker: str,
    *,
    text: str = "",
    addressed: tuple[str, ...] = (),
    accused: tuple[str, ...] = (),
    defended: tuple[str, ...] = (),
    claims: Role | None = None,
) -> StatementMade:
    return StatementMade(
        speaker=speaker,
        text=text or f"{speaker} speaks.",
        part="open_floor",
        addressed=addressed,
        accused=accused,
        defended=defended,
        claimed_role=claims,
    )


def suspects(resident: str, **levels: int) -> ReflectionWritten:
    """A reflection suspecting each Resident named (by variable) at the given level."""
    names = {"c1": C1, "c2": C2, "c3": C3, "doc": DOC, "det": DET, "sheriff": SHERIFF}
    suspicions = tuple(
        Suspicion(resident=names[who], suspicion=level, note=f"{who} at {level}")
        for who, level in levels.items()
    )
    return ReflectionWritten(
        resident=resident, journal_entry="", notebook="", suspicions=suspicions
    )


def ballot(voter: str, target: str | None) -> BallotCast:
    return BallotCast(voter=voter, target=target)
