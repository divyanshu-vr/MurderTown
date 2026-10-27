"""A readable, Spectator's-eye transcript of a game, for the terminal.

The console only needs plain ASCII, so the transcript avoids box-drawing
characters that some Windows terminals cannot print.
"""

from mm.engine.events import (
    BallotCast,
    Event,
    GameEnded,
    GameStarted,
    PhaseStarted,
    ResidentDied,
    RoleAssigned,
    StatementMade,
    VoteResolved,
)


def describe(event: Event) -> str:
    match event.payload:
        case GameStarted(residents=residents):
            names = ", ".join(resident.name for resident in residents)
            return f"{len(residents)} Residents move into town: {names}."
        case RoleAssigned(resident=resident, role=role, teammates=teammates):
            partners = f" (with {', '.join(teammates)})" if teammates else ""
            return f"  {resident} is secretly a {role.capitalize()}{partners}."
        case PhaseStarted(day=day, phase=phase):
            return f"\n=== Day {day}: {phase.capitalize()} ==="
        case StatementMade(speaker=speaker, text=text):
            return f'{speaker}: "{text}"'
        case BallotCast(voter=voter, choice=choice):
            return f"  {voter} votes {choice}"
        case VoteResolved(tally=tally, banished=banished):
            counts = ", ".join(f"{name} {votes}" for name, votes in tally.items())
            result = f"{banished} is banished." if banished else "Nobody is banished."
            return f"Tally: {counts}. {result}"
        case ResidentDied(resident=resident, role=role):
            return f"{resident} leaves the town forever. They were a {role.capitalize()}."
        case GameEnded(winner=winner, reason=reason):
            return f"\n*** The {winner} win. {reason} ***"
