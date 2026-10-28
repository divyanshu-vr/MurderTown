"""A sliding-window rate limit, for what the Host may do only so often."""

import time
from collections import deque


class RateLimit:
    """At most `times` in any `per_seconds`."""

    def __init__(self, times: int, per_seconds: float) -> None:
        self.times, self.per_seconds = times, per_seconds
        self._taken: deque[float] = deque()

    def take(self) -> float:
        """Take a turn now and return 0, or, if none is free, the seconds until one is."""
        now = time.monotonic()
        while self._taken and self._taken[0] <= now - self.per_seconds:
            self._taken.popleft()
        if len(self._taken) >= self.times:
            return self._taken[0] + self.per_seconds - now
        self._taken.append(now)
        return 0.0

    def give_back(self) -> None:
        """Give back the last turn taken, for something that did not happen after all."""
        self._taken.pop()
