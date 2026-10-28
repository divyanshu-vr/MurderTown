"""The game's append-only event log.

Appending a payload applies it to the true state first, then stamps it with its
sequence number, Day, Phase and the decision that caused it, so every event
records the moment it belongs to. Observers (storage, the live stream) hear
about each event in the order they were registered, before the game moves on.
"""

from collections.abc import Awaitable, Callable, Sequence

from mm.engine.events import Event, EventPayload
from mm.engine.state import GameState

EventObserver = Callable[[Event], Awaitable[None]]


class EventLog:
    def __init__(self, observers: Sequence[EventObserver] = ()) -> None:
        self.events: list[Event] = []
        self.state = GameState()
        self.observers = tuple(observers)

    async def append(self, payload: EventPayload, decision_id: str | None = None) -> Event:
        self.state.apply(payload)
        event = self._stamped(payload, len(self.events) + 1, decision_id)
        self.events.append(event)
        for observer in self.observers:
            await observer(event)
        return event

    def unlogged(self, payload: EventPayload) -> Event:
        """Something already heard but not in the log yet, such as a Dusk message whose
        wave has not finished. Its sequence number is 0 until it is appended."""
        return self._stamped(payload, seq=0, decision_id=None)

    def _stamped(self, payload: EventPayload, seq: int, decision_id: str | None) -> Event:
        return Event(
            seq=seq,
            day=self.state.day,
            phase=self.state.phase,
            visibility=payload.visibility(),
            decision_id=decision_id,
            payload=payload,
        )
