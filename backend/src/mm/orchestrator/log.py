"""The game's append-only event log.

Appending a payload applies it to the true state first, then stamps it with its
sequence number, Day and Phase, so every event records the moment it belongs to.
Observers (storage, the live stream) hear about each event in the order they
were registered, before the game moves on.
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

    async def append(self, payload: EventPayload) -> Event:
        self.state.apply(payload)
        event = Event(
            seq=len(self.events) + 1,
            day=self.state.day,
            phase=self.state.phase,
            visibility=payload.visibility(),
            payload=payload,
        )
        self.events.append(event)
        for observer in self.observers:
            await observer(event)
        return event
