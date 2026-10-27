"""The live bus: fans a game's new events out to everyone watching it.

The game store is the source of truth; the bus only carries news. The API runs
in one process today, so the bus lives in memory. A Redis-backed bus can
replace it behind the same interface when the API runs on several workers.
"""

import asyncio
from collections import defaultdict
from collections.abc import Iterator
from contextlib import AbstractContextManager, contextmanager
from typing import Protocol

from mm.engine.events import Event


class Bus(Protocol):
    async def publish(self, game_id: str, event: Event) -> None: ...

    def subscribe(self, game_id: str) -> AbstractContextManager["asyncio.Queue[Event]"]: ...


class InProcessBus:
    def __init__(self) -> None:
        self._subscribers: defaultdict[str, set[asyncio.Queue[Event]]] = defaultdict(set)

    async def publish(self, game_id: str, event: Event) -> None:
        for queue in self._subscribers.get(game_id, ()):
            queue.put_nowait(event)

    @contextmanager
    def subscribe(self, game_id: str) -> Iterator["asyncio.Queue[Event]"]:
        queue: asyncio.Queue[Event] = asyncio.Queue()
        self._subscribers[game_id].add(queue)
        try:
            yield queue
        finally:
            self._subscribers[game_id].discard(queue)
            if not self._subscribers[game_id]:
                del self._subscribers[game_id]
