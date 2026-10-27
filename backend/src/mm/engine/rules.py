"""Rules that judge decisions and decide when the game is over."""

from dataclasses import dataclass

from mm.engine.decisions import Ballot, Decision, DecisionRequest, Reflection, Statement
from mm.engine.roles import Role, Side
from mm.engine.state import GameState


def why_illegal(request: DecisionRequest, decision: Decision) -> str | None:
    """Why a decision breaks the rules for its request, or None if it is legal."""
    match decision:
        case Ballot(choice=choice) if choice not in request.options:
            return f"{choice!r} is not one of the options {list(request.options)}"
        case Statement(text=text) if not text.strip():
            return "a Statement cannot be empty"
        case Reflection(suspicions=suspicions):
            return _suspicions_problem([s.resident for s in suspicions], request.options)
    return None


def _suspicions_problem(named: list[str], options: tuple[str, ...]) -> str | None:
    if strays := sorted(set(named) - set(options)):
        return f"suspicions may only name {list(options)}, not {strays}"
    if len(named) != len(set(named)):
        return "name each Resident at most once in your suspicions"
    return None


@dataclass(frozen=True)
class Verdict:
    winner: Side
    reason: str


def verdict(state: GameState) -> Verdict | None:
    """Checked after every Phase: has either side already won?

    Needs the true state, because only it knows every living Resident's role.
    """
    murderers = sum(state.roles[name] is Role.MURDERER for name in state.living)
    if murderers == 0:
        return Verdict(Side.TOWN, "Every Murderer is gone.")
    if murderers >= len(state.living) - murderers:
        return Verdict(Side.MURDERERS, "The Murderers now equal the rest of the town.")
    return None


def verdict_at_end_of_day(state: GameState) -> Verdict | None:
    """Checked when a Day is over: the game ends after the last allowed Day."""
    assert state.config is not None
    if state.day >= state.config.max_days:
        return Verdict(Side.MURDERERS, "The town ran out of days.")
    return None
