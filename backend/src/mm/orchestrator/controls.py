"""The Host's controls over a game being played: pause, step and resume, and the halt a shutdown
uses. They act at checkpoints, before each batch of decisions, so a batch is never split.

Pausing changes when a game's events happen, never what they are, so it is not in the event
log: a paused game, resumed, ends with the same log it would have had.
"""

import asyncio
import time
from collections.abc import Callable


class GameHaltedError(Exception):
    """The game was asked to stop before its next decision, so it can resume later."""


class GameControls:
    """Holds a game at its checkpoints while it is paused. A step lets one more batch of
    decisions through and holds again; a halt (a shutdown) stops the game at its next
    checkpoint, paused or not, so it can resume when the server starts again.

    Time held at a checkpoint is not game time: the Open floor's clock stops with the game.
    """

    def __init__(
        self, clock: Callable[[], float] = time.monotonic, *, paused: bool = False
    ) -> None:
        self._clock = clock
        self.paused = paused
        self._steps = 0
        self._halted = False
        self._held_for = 0.0
        self._changed = asyncio.Event()

    def pause(self) -> None:
        self.paused = True

    def resume(self) -> None:
        self.paused, self._steps = False, 0
        self._changed.set()

    def step(self) -> None:
        """Let one more batch of decisions through a paused game."""
        self._steps += 1
        self._changed.set()

    def halt(self) -> None:
        self._halted = True
        self._changed.set()

    def now(self) -> float:
        """The game's clock: the wall clock, less the time the game was held."""
        return self._clock() - self._held_for

    async def checkpoint(self, replaying: bool = False) -> None:
        """Wait here while the game is paused, unless a step lets this batch through. A game
        replaying its stored log is never held: it catches up first. A halt raises
        `GameHaltedError`, waking a held game."""
        while not self._halted:
            if replaying or not self.paused:
                return
            if self._steps:
                self._steps -= 1
                return
            held_since = self._clock()
            self._changed.clear()
            await self._changed.wait()
            self._held_for += self._clock() - held_since
        raise GameHaltedError
