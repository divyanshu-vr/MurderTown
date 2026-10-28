"""How an evaluation's report writes numbers into Markdown tables."""

import math
from collections.abc import Sequence

from mm.agents import ModelCall
from mm.review.rates import Rate

FEW = 30
"""Fewer trials or games than this, and a rate's interval is too wide to say much: marked *."""


def rate_cells(rate: Rate) -> str:
    """A rate, its interval and its trials, as three cells of a table."""
    if rate.value is None or rate.interval is None:
        return f"– | – | {count(rate.trials)}"
    low, high = rate.interval
    return f"{percent(rate.value)} | {percent(low)} to {percent(high)} | {count(rate.trials)}"


def rate_with_interval(rate: Rate, of: str) -> str:
    """A rate, its interval and what it rests on, in one cell."""
    if rate.value is None or rate.interval is None:
        return "–"
    low, high = rate.interval
    return f"{percent(rate.value)} ({percent(low)} to {percent(high)}; {count(rate.trials)} {of})"


def share_of(rate: Rate) -> str:
    """A rate and how many trials it rests on, in one cell."""
    return f"{percent(rate.value)} of {count(rate.trials)}"


def count(number: int) -> str:
    return f"{number}*" if number < FEW else str(number)


def dollars(amount: float) -> str:
    return f"${amount:,.4f}"


def percent(share: float | None) -> str:
    return "–" if share is None else f"{share:.1%}"


def latency(calls: Sequence[ModelCall]) -> str:
    """How long the calls took: their median and 95th percentile."""
    took = [call.latency_ms for call in calls]
    median, slow = percentile(took, 50), percentile(took, 95)
    if median is None or slow is None:
        return "–"
    return f"{median:,.0f} ms median, {slow:,.0f} ms at the 95th percentile"


def percentile(values: Sequence[float], at: int) -> float | None:
    """The smallest value with at least `at`% of the values at or below it (nearest rank)."""
    if not values:
        return None
    rank = math.ceil(at / 100 * len(values))
    return sorted(values)[max(rank, 1) - 1]
