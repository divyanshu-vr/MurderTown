"""The game's append-only event log.

Appending a payload applies it to the true state first, then stamps it with its
sequence number, Day, Phase and the decision that caused it, so every event
records the moment it belongs to. Observers (storage, the live stream) hear
about each event in the order they were registered, before the game moves on.

A resumed game replays from the start over the events it had already stored:
each event it makes again must equal the stored one, and observers do not hear
it twice. Past the end of the stored log, the game goes on as usual.
"""

from collections.abc import Awaitable, Callable, Sequence

from mm.engine.events import Event, EventPayload
from mm.engine.state import GameState

EventObserver = Callable[[Event], Awaitable[None]]


class ReplayDivergedError(Exception):
    """A resumed game made a different event from the one it had stored at the same place."""

    def __init__(self, stored: Event, made: Event) -> None:
        super().__init__(
            f"event {stored.seq} was {stored.model_dump_json()} but the replay made "
            f"{made.model_dump_json()}"
        )
        self.seq, self.stored, self.made = stored.seq, stored, made


class EventLog:
    def __init__(
        self, observers: Sequence[EventObserver] = (), replay: Sequence[Event] = ()
    ) -> None:
        self.events: list[Event] = []
        self.state = GameState()
        self.observers = tuple(observers)
        self.replay = tuple(replay)
        """The stored events a resumed game must make again; empty once it has caught up."""

    @property
    def replaying(self) -> bool:
        return bool(self.replay)

    def upcoming(self) -> Event | None:
        """While replaying, the stored event that comes next: what the game did at this point
        before it stopped, for decisions the replay cannot make again (such as the clock's)."""
        made = len(self.events)
        return self.replay[made] if made < len(self.replay) else None

    async def append(self, payload: EventPayload, decision_id: str | None = None) -> Event:
        self.state.apply(payload)
        event = self._stamped(payload, len(self.events) + 1, decision_id)
        self.events.append(event)
        if self.replaying:
            if (stored := self.replay[event.seq - 1]) != event:
                self.stop_replaying()
                raise ReplayDivergedError(stored, event)
            if event.seq == len(self.replay):
                self.replay = ()  # caught up: from here on the game is live
            return event  # stored and published before the game stopped
        for observer in self.observers:
            await observer(event)
        return event

    def stop_replaying(self) -> None:
        """Go back to the stored log, so whatever is appended next (an abort) follows it."""
        if self.replaying:
            self.events, self.state = list(self.replay), GameState.fold(self.replay)
            self.replay = ()

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
