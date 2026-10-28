"""The post-game review: what changed the game, who lied, and whose accusations others followed.

One pure function over a game's full log, which the API serves and `mm play --out` and
`mm export` write beside a game file, and which the evaluation harness is to reuse. A
Resident's private belief about another is what they know, if they are a Murderer (their
teammates are Murderers, everyone else is not), or else their latest suspicion of them, by the
same rule as their prompts (`remember`).
"""

from collections.abc import Callable, Sequence
from typing import Annotated, Literal

from pydantic import BaseModel, Field

from mm.agents.memory import remember
from mm.engine import Role
from mm.engine.decisions import Suspicion
from mm.engine.events import (
    PROTOCOL,
    BallotCast,
    Event,
    ReflectionWritten,
    ResidentDied,
    SheriffFired,
    StatementMade,
)
from mm.engine.state import GameState

TRUSTS_AT_MOST = 30
"""A suspicion this low or lower means the Resident privately trusts the other."""

SUSPECTS_AT_LEAST = 70
"""A suspicion this high or higher means the Resident privately suspects the other."""

SWINGS_AT_LEAST = 40
"""One reflection changing a suspicion by this much or more is a turning point."""

KNOWS_GUILTY = "knows them to be a fellow Murderer"
KNOWS_INNOCENT = "knows they are no Murderer"


class TurningEvent(BaseModel):
    """A death or the Sheriff's shot: the event at `seq`."""

    model_config = PROTOCOL

    kind: Literal["event"] = "event"
    seq: int


class Swing(BaseModel):
    """One reflection (at `seq`) moving a Resident's suspicion of another a long way at once."""

    model_config = PROTOCOL

    kind: Literal["swing"] = "swing"
    seq: int
    resident: str
    suspect: str
    before: int
    after: int


TurningPoint = Annotated[TurningEvent | Swing, Field(discriminator="kind")]


class FalseClaim(BaseModel):
    """A Statement claiming a role that is not the speaker's."""

    model_config = PROTOCOL

    kind: Literal["false_role"] = "false_role"
    seq: int
    speaker: str
    said: str
    claimed_role: Role
    true_role: Role


LieAboutKind = Literal["accused_trusted", "defended_suspected"]


class LieAbout(BaseModel):
    """A Statement accusing someone the speaker trusts, or defending someone they suspect,
    beside what the speaker privately held about them."""

    model_config = PROTOCOL

    kind: LieAboutKind
    seq: int
    speaker: str
    said: str
    belief: Suspicion


Lie = Annotated[FalseClaim | LieAbout, Field(discriminator="kind")]


class Influence(BaseModel):
    """How many of the others' ballots (`followed`) went against someone this Resident had
    accused that Day, out of all the others' `ballots` on the Days they accused anyone before
    a Vote. A vote to skip is a ballot that follows nobody."""

    model_config = PROTOCOL

    resident: str
    followed: int
    ballots: int


class Review(BaseModel):
    model_config = PROTOCOL

    turning_points: list[TurningPoint]
    lies: list[Lie]
    influence: list[Influence]
    """Most followed first (ties: more ballots, then by name). A Resident who accused nobody on
    a Day with a Vote is not ranked."""


def review_of(events: Sequence[Event]) -> Review:
    return Review(
        turning_points=_turning_points(events),
        lies=_lies(events),
        influence=_influence(events),
    )


def _turning_points(events: Sequence[Event]) -> list[TurningPoint]:
    points: list[TurningPoint] = []
    for index, event in enumerate(events):
        payload = event.payload
        if isinstance(payload, ResidentDied | SheriffFired):
            points.append(TurningEvent(seq=event.seq))
        elif isinstance(payload, ReflectionWritten):
            earlier = _suspicions(events[:index], payload.resident)
            for now in payload.suspicions:
                before = earlier.get(now.resident)
                if before and abs(now.suspicion - before.suspicion) >= SWINGS_AT_LEAST:
                    swing = Swing(
                        seq=event.seq,
                        resident=payload.resident,
                        suspect=now.resident,
                        before=before.suspicion,
                        after=now.suspicion,
                    )
                    points.append(swing)
    return points


def _trusts(suspicion: int) -> bool:
    return suspicion <= TRUSTS_AT_MOST


def _suspects(suspicion: int) -> bool:
    return suspicion >= SUSPECTS_AT_LEAST


JUDGED: tuple[
    tuple[LieAboutKind, Callable[[StatementMade], tuple[str, ...]], Callable[[int], bool]], ...
] = (
    ("accused_trusted", lambda said: said.accused, _trusts),
    ("defended_suspected", lambda said: said.defended, _suspects),
)
"""Who a Statement names, and the private suspicion of them that would make it a lie."""


def _lies(events: Sequence[Event]) -> list[Lie]:
    roles = GameState.fold(events).roles
    state = GameState()
    lies: list[Lie] = []
    claims_told: set[tuple[str, Role]] = set()
    for index, event in enumerate(events):
        said = event.payload
        if isinstance(said, StatementMade):
            speaker, true_role, claim = said.speaker, roles[said.speaker], said.claimed_role
            if claim and claim is not true_role and (speaker, claim) not in claims_told:
                claims_told.add((speaker, claim))
                lies.append(
                    FalseClaim(
                        seq=event.seq,
                        speaker=speaker,
                        said=said.text,
                        claimed_role=claim,
                        true_role=true_role,
                    )
                )
            for kind, named, contradicts in JUDGED:
                for about in named(said):
                    if about in state.dead:
                        continue
                    belief = _belief(events[:index], roles, speaker, about)
                    if belief and contradicts(belief.suspicion):
                        lie = LieAbout(
                            kind=kind, seq=event.seq, speaker=speaker, said=said.text, belief=belief
                        )
                        lies.append(lie)
        state.apply(said)
    return lies


def _suspicions(before: Sequence[Event], resident: str) -> dict[str, Suspicion]:
    """A Resident's latest suspicion of each other, as their dossier stood then."""
    return {suspicion.resident: suspicion for suspicion in remember(before, resident).dossier}


def _belief(
    before: Sequence[Event], roles: dict[str, Role], speaker: str, about: str
) -> Suspicion | None:
    """What the speaker privately believed about another just then, if anything."""
    if roles[speaker] is Role.MURDERER:
        guilty = roles.get(about) is Role.MURDERER
        note = KNOWS_GUILTY if guilty else KNOWS_INNOCENT
        return Suspicion(resident=about, suspicion=100 if guilty else 0, note=note)
    return _suspicions(before, speaker).get(about)


def _influence(events: Sequence[Event]) -> list[Influence]:
    state = GameState()
    accused: dict[tuple[int, str], set[str]] = {}
    ballots: dict[int, list[BallotCast]] = {}
    for event in events:
        payload = event.payload
        if isinstance(payload, StatementMade):
            named = {name for name in payload.accused if name not in state.dead}
            accused.setdefault((event.day, payload.speaker), set()).update(named)
        elif isinstance(payload, BallotCast):
            ballots.setdefault(event.day, []).append(payload)
        state.apply(payload)

    followed: dict[str, int] = {}
    cast: dict[str, int] = {}
    for (day, accuser), targets in accused.items():
        others = [b for b in ballots.get(day, []) if b.voter != accuser]
        if not targets or not others:
            continue
        followed[accuser] = followed.get(accuser, 0) + sum(b.target in targets for b in others)
        cast[accuser] = cast.get(accuser, 0) + len(others)
    ranked = [
        Influence(resident=name, followed=followed[name], ballots=cast[name]) for name in cast
    ]
    return sorted(ranked, key=lambda i: (-i.followed / i.ballots, -i.ballots, i.resident))
