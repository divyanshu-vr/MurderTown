"""A readable, Spectator's-eye transcript of a game, for the terminal.

The console only needs plain ASCII, so the transcript avoids box-drawing
characters that some Windows terminals cannot print.
"""

from mm.engine import Side
from mm.engine.events import (
    BallotCast,
    BidPlaced,
    DecisionFellBack,
    Event,
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

VICTORY = {Side.TOWN: "The Town wins.", Side.MURDERERS: "The Murderers win."}


def describe(event: Event) -> str | None:  # noqa: C901, PLR0912 - one case per event type
    """One readable line per event, or None for events not worth printing (quiet bids)."""
    match event.payload:
        case GameStarted(residents=residents):
            names = ", ".join(f"{r.name} the {r.occupation}" for r in residents)
            return f"{len(residents)} Residents move into town: {names}."
        case RoleAssigned(resident=resident, role=role, teammates=teammates):
            partners = f" (with {', '.join(teammates)})" if teammates else ""
            return f"  {resident} is secretly a {role.capitalize()}{partners}."
        case PhaseStarted(day=day, phase=phase):
            return f"\n=== Day {day}: {phase.capitalize()} ==="
        case BidPlaced(resident=resident, urgency=urgency, reason=reason):
            return f"  ({resident} bids {urgency}: {reason})" if urgency else None
        case StatementMade(speaker=speaker, text=text):
            return f'{speaker}: "{text}"'
        case SheriffFired(sheriff=sheriff, target=target):
            return f"BANG! {sheriff}, the Sheriff, fires at {target}."
        case SheriffHeldFire(sheriff=sheriff):
            return f"  ({sheriff}, the Sheriff, holds fire.)"
        case LastWordsSpoken(resident=resident, text=text):
            return f'{resident}\'s last words: "{text}"'
        case BallotCast(voter=voter, target=target):
            return f"  {voter} votes for {target}" if target else f"  {voter} votes to skip"
        case VoteResolved(tally=tally, skips=skips, banished=banished):
            counts = [f"{name} {votes}" for name, votes in tally.items()] + [f"skip {skips}"]
            result = f"{banished} is banished." if banished else "Nobody is banished."
            return f"Tally: {', '.join(counts)}. {result}"
        case ResidentDied(resident=resident, cause=cause, role=role):
            how = {"banished": "leaves the town forever", "shot": "falls to the Sheriff's bullet",
                   "backfire": "is struck down by the backfire"}[cause]  # fmt: skip
            return f"{resident} {how}. They were a {role.capitalize()}."
        case ReflectionWritten(resident=resident, journal_entry=entry):
            return f"  ({resident} writes privately: {entry})"
        case DecisionFellBack(resident=resident, kind=kind, reason=reason):
            return f"  [fallback] {resident}'s {kind} used a safe default: {reason}"
        case GameEnded(winner=winner, reason=reason):
            return f"\n*** {VICTORY[winner]} {reason} ***"
