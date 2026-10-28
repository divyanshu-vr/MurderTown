"""Rates: how often something happened, with its 95% Wilson interval."""

import pytest

from mm.review.rates import Rate


@pytest.mark.parametrize(
    ("successes", "trials", "low", "high"),
    [  # Newcombe (1998), Statistics in Medicine 17:857-872, table I, method 3
        (81, 263, 0.2553, 0.3662),
        (15, 148, 0.0624, 0.1605),
        (0, 20, 0.0, 0.1611),
        (1, 29, 0.0061, 0.1718),
    ],
)
def test_a_rate_has_the_95_percent_wilson_interval(
    successes: int, trials: int, low: float, high: float
) -> None:
    rate = Rate(successes=successes, trials=trials)

    assert rate.interval == pytest.approx((low, high), abs=5e-5)
    assert rate.value == pytest.approx(successes / trials)


def test_a_rate_of_nothing_has_no_value_and_no_interval() -> None:
    rate = Rate(successes=0, trials=0)

    assert (rate.value, rate.interval) == (None, None)


def test_rates_pool_by_adding_successes_and_trials() -> None:
    pooled = Rate(successes=3, trials=4) + Rate(successes=1, trials=6)

    assert pooled == Rate(successes=4, trials=10)
    assert pooled.value == pytest.approx(0.4)
