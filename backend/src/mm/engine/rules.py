"""Rules that judge decisions, limit what a Resident may say, and decide when the game is over."""

from collections.abc import Iterable
from dataclasses import dataclass

from mm.engine.decisions import (
    ConversationMessage,
    Decision,
    DecisionRequest,
    DenMessage,
    Recap,
    Reflection,
    Showdown,
    Statement,
    Target,
)
from mm.engine.roles import Role, Side
from mm.engine.state import GameState


def why_illegal(request: DecisionRequest, decision: Decision) -> str | None:
    """Why a decision breaks the rules for its request, or None if it is legal."""
    match decision:
        case Target(target=target) if target not in request.options:
            return f"{target!r} is not one of the options {list(request.options)}"
        case (
            Statement(text=text)
            | DenMessage(text=text)
            | Recap(text=text)
            | ConversationMessage(text=text)
        ) if not text.strip():
            return "the text cannot be empty"
        case Reflection(suspicions=suspicions):
            return _suspicions_problem([s.resident for s in suspicions], request.options)
        case Showdown(fire=True, target=target) if target not in request.options:
            return f"to fire, name one of {list(request.options)} as the target, not {target!r}"
    return None


WORD_LIMIT = 90
"""The most words a Resident may say at once, in a Statement or in their last words.

Prompts ask for fewer words than this, so an ordinary answer is never cut and
the limit only stops a runaway answer from flooding the town. A long answer is
cut rather than retried, because a retry would cost another model call.
"""


def trimmed(text: str) -> str:
    """What a Resident said, cut to the word limit."""
    words = text.split()
    if len(words) <= WORD_LIMIT:
        return text.strip()
    return " ".join(words[:WORD_LIMIT]) + "..."


def named(names: Iterable[str], allowed: Iterable[str]) -> tuple[str, ...]:
    """The allowed names among those given, each once, in the order given.

    Names a Resident gives (whom a Statement addresses, whom they want to talk to)
    are filtered rather than rejected: a stray name costs nothing, while a retry
    would cost another model call.
    """
    permitted = set(allowed)
    return tuple(dict.fromkeys(name for name in names if name in permitted))


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
    murderers = len(state.living_as(Role.MURDERER))
    if murderers == 0:
        return Verdict(Side.TOWN, "Every Murderer is gone.")
    if murderers >= len(state.living) - murderers:
        return Verdict(Side.MURDERERS, "The Murderers now equal the rest of the town.")
    return None


def verdict_at_end_of_day(state: GameState) -> Verdict | None:
    """Checked when a Day is over: the game ends after the last allowed Day."""
    assert state.rules is not None
    if state.day >= state.rules.max_days:
        return Verdict(Side.MURDERERS, "The town ran out of days.")
    return None
