"""Perception: the only way any Resident learns anything.

Every prompt, every bot decision and every Mind inspector view is built from
`perceived_by`, so information isolation is enforced in this one function.
"""

from collections.abc import Iterable, Sequence

from mm.engine.events import Event, PhaseStarted, ReflectionWritten, RoleAssigned
from mm.engine.phases import Phase


def perceived_by(events: Iterable[Event], resident: str) -> list[Event]:
    """The events one Resident may perceive, in log order."""
    return [event for event in events if event.visibility.allows(resident)]


def since_last_reflection(view: Sequence[Event], resident: str) -> list[Event]:
    """What a Resident has perceived since they last wrote a reflection (everything, if never)."""
    reflected = [
        index
        for index, event in enumerate(view)
        if isinstance(event.payload, ReflectionWritten) and event.payload.resident == resident
    ]
    return list(view[reflected[-1] + 1 :] if reflected else view)


def has_news(view: Sequence[Event], resident: str) -> bool:
    """Whether anything worth reflecting on happened since the last reflection.

    Casting and Phase changes alone are not news.
    """
    return any(
        event.phase is not Phase.SETUP and not isinstance(event.payload, PhaseStarted)
        for event in since_last_reflection(view, resident)
    )


def briefing(view: Sequence[Event], resident: str) -> RoleAssigned:
    """The Resident's own role assignment: their role, persona and any teammates."""
    return next(
        event.payload
        for event in view
        if isinstance(event.payload, RoleAssigned) and event.payload.resident == resident
    )
