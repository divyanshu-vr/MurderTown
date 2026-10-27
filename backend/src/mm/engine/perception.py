"""Perception: the only way any Resident learns anything.

Every prompt, every bot decision and every Mind inspector view is built from
`perceived_by`, so information isolation is enforced in this one function.
"""

from collections.abc import Iterable

from mm.engine.events import Event


def perceived_by(events: Iterable[Event], resident: str) -> list[Event]:
    """The events one Resident may perceive, in log order."""
    return [event for event in events if event.visibility.allows(resident)]
