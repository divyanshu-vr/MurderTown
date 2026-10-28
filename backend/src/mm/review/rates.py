"""How often something happened in a game, as successes out of trials, with its 95% Wilson interval.

Rates of many games pool by adding (all successes over all trials) rather than averaging, so a
game with many trials counts for more than one with few, and the interval says how sure it is.
"""

import math
from typing import Self

from pydantic import BaseModel, ConfigDict

Z_95 = 1.959964
"""How many standard deviations either side of the mean hold 95% of a normal distribution."""


class Rate(BaseModel):
    """How often something happened: `successes` out of `trials`."""

    model_config = ConfigDict(frozen=True)

    successes: int = 0
    trials: int = 0

    @property
    def value(self) -> float | None:
        return self.successes / self.trials if self.trials else None

    @property
    def interval(self) -> tuple[float, float] | None:
        """The 95% Wilson score interval, which stays within 0 to 1 and holds up for small
        samples and for rates near 0 or 1, where the textbook interval does not."""
        if not self.trials:
            return None
        n, p, z = self.trials, self.successes / self.trials, Z_95
        middle = (p + z * z / (2 * n)) / (1 + z * z / n)
        half = z / (1 + z * z / n) * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
        return max(0.0, middle - half), min(1.0, middle + half)

    def __add__(self, other: Self) -> Self:
        return type(self)(
            successes=self.successes + other.successes, trials=self.trials + other.trials
        )
