"""Rules of the Sheriff's single bullet.

The Sheriff may fire once per game. Hitting a Murderer kills them; hitting a
Town Resident kills that Resident and, by the backfire, the Sheriff too. Every
shot is public, and so is every death, so the town always knows whether the
bullet is still in play.
"""

from mm.engine.events import EventPayload, ResidentDied, SheriffFired
from mm.engine.roles import Role
from mm.engine.state import GameState


def armed_sheriff(state: GameState) -> str | None:
    """The living Sheriff, if they still hold the bullet. Needs the true state."""
    sheriffs = state.living_as(Role.SHERIFF)
    return sheriffs[0] if sheriffs and not state.bullet_spent else None


def shot_options(state: GameState, sheriff: str) -> tuple[str, ...]:
    """Every other living Resident."""
    return state.others_living(sheriff)


def shot_events(state: GameState, sheriff: str, target: str) -> list[EventPayload]:
    """What a shot causes, in order: the shot, the target's death, then any backfire."""
    target_role = state.roles[target]
    hit = target_role is Role.MURDERER
    events: list[EventPayload] = [
        SheriffFired(sheriff=sheriff, target=target, hit_a_murderer=hit),
        ResidentDied(resident=target, cause="shot", role=target_role),
    ]
    if not hit:
        events.append(ResidentDied(resident=sheriff, cause="backfire", role=Role.SHERIFF))
    return events
