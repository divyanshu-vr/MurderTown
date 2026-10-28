"""Rules of the Night: whom the Murderers may kill, the Doctor protect and the Detective
investigate, and what Dawn then reveals.

Protection is resolved before the kill, so a protected Victim survives. The
Doctor may never protect the same Resident two Nights running, and themselves
only once per game. The Detective never investigates anyone twice, and their
finding is right only as often as the game's `detective_accuracy` says.
"""

from random import Random

from mm.engine.events import AttackThwarted, EventPayload, ResidentDied
from mm.engine.roles import Role
from mm.engine.state import GameState


def kill_options(state: GameState) -> tuple[str, ...]:
    """Every living Resident who is not a Murderer."""
    return tuple(name for name in state.living if state.roles[name] is not Role.MURDERER)


def den_proposal(proposal: str | None, options: tuple[str, ...]) -> str | None:
    """The Victim a Den message proposes, if it is one the Murderers may kill.

    Any other name is dropped rather than retried: the message still counts, and
    a retry would cost another model call for a proposal that binds nobody.
    """
    return proposal if proposal in options else None


def protect_options(state: GameState, doctor: str) -> tuple[str, ...]:
    """Every living Resident, except last Night's protected and, after once, the Doctor."""
    last_night = state.protections.get(state.day - 1)
    protected_themselves = doctor in state.protections.values()
    return tuple(
        name
        for name in state.living
        if name != last_night and not (name == doctor and protected_themselves)
    )


def investigate_options(state: GameState, detective: str) -> tuple[str, ...]:
    """Every other living Resident the Detective has not investigated yet."""
    return tuple(name for name in state.others_living(detective) if name not in state.investigated)


def investigation_finding(is_murderer: bool, accuracy: float, rng: Random) -> bool:
    """Whether the Detective is told "murderer": the truth with probability `accuracy`."""
    return is_murderer if rng.random() < accuracy else not is_murderer


def dawn_news(state: GameState) -> list[EventPayload]:
    """What Dawn announces about the Night before: the murder, or a thwarted attack."""
    assert state.config is not None
    night = state.day - 1
    victim = state.victims.get(night)
    if victim is None:
        return []
    if state.protections.get(night) == victim:
        return [AttackThwarted(saved=victim if state.config.dawn_names_the_saved else None)]
    return [ResidentDied(resident=victim, cause="murdered", role=state.roles[victim])]
