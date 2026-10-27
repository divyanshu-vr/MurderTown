"""Seam 1 input: the Host's configuration is checked before any game starts."""

import pytest
from pydantic import ValidationError

from mm.engine import GameConfig


@pytest.mark.parametrize(
    ("residents", "murderers"),
    [
        pytest.param(5, 1, id="too few Residents"),
        pytest.param(16, 3, id="too many Residents"),
        pytest.param(12, 0, id="no Murderers"),
        pytest.param(15, 4, id="more than three Murderers"),
        pytest.param(11, 3, id="more than a quarter of the town"),
    ],
)
def test_a_configuration_outside_the_bounds_is_rejected(residents: int, murderers: int) -> None:
    with pytest.raises(ValidationError):
        GameConfig(residents=residents, murderers=murderers)


@pytest.mark.parametrize(
    ("residents", "murderers"),
    [(6, 1), (8, 2), (12, 3), (15, 3)],
)
def test_a_configuration_inside_the_bounds_is_accepted(residents: int, murderers: int) -> None:
    assert GameConfig(residents=residents, murderers=murderers).murderers == murderers
