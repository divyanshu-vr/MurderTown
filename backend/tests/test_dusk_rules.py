"""Table tests for the rules of Dusk: who pairs with whom, and who speaks next.

`pair_up` takes the talkers in a random order. These tables use a stand-in random
source that keeps the order given (or reverses it), so each row has one answer.
"""

from collections.abc import MutableSequence
from random import Random
from typing import Any

import pytest

from mm.engine.decisions import DuskIntent
from mm.engine.dusk import Pair, as_seen, next_speaker, pair_up, partner_of, settled
from mm.engine.rules import named


class InOrder(Random):
    """A random source whose shuffle leaves the order as it is."""

    def shuffle(self, x: MutableSequence[Any]) -> None:  # type: ignore[override]
        pass


class Reversed(Random):
    """A random source whose shuffle reverses the order."""

    def shuffle(self, x: MutableSequence[Any]) -> None:  # type: ignore[override]
        x.reverse()


@pytest.mark.parametrize(
    ("wanted", "pairs"),
    [
        pytest.param({"A": ["B", "C"]}, [("A", "B")], id="a talker gets their first preference"),
        pytest.param(
            {"A": ["X"], "B": ["X", "D"]},
            [("A", "X"), ("B", "D")],
            id="a Resident already approached is skipped for the next preference",
        ),
        pytest.param(
            {"A": ["B"], "C": ["A", "D"]},
            [("A", "B"), ("C", "D")],
            id="a Resident who asked is not approached",
        ),
        pytest.param(
            {"A": ["X"], "B": ["X", "A"], "C": ["X"]},
            [("A", "X")],
            id="a talker whose every preference is taken talks to nobody",
        ),
        pytest.param(
            {"A": ["B"], "B": ["A", "C"]},
            [("A", "B")],
            id="two who name each other talk once",
        ),
        pytest.param(
            {"A": ["X"], "X": ["C"]},
            [("A", "X")],
            id="a Resident already approached does not start their own",
        ),
        pytest.param({"A": ["W"]}, [("A", "W")], id="a wanderer can be approached"),
        pytest.param({}, [], id="nobody wants to talk"),
    ],
)
def test_pairing(wanted: dict[str, list[str]], pairs: list[Pair]) -> None:
    assert pair_up(wanted, InOrder()) == pairs


def test_the_order_the_talkers_come_in_decides_who_gets_a_busy_resident() -> None:
    wanted = {"A": ["X"], "B": ["X"], "C": ["X"]}

    assert pair_up(wanted, Reversed()) == [("C", "X")]


def test_pairing_nobody_draws_nothing_from_the_random_source() -> None:
    rng = Random(7)
    before = rng.getstate()

    pair_up({}, rng)

    assert rng.getstate() == before


@pytest.mark.parametrize(
    ("said", "ended", "speaker"),
    [
        (0, False, "Asker"),
        (1, False, "Asked"),
        (2, False, "Asker"),
        (3, False, "Asked"),
        (4, False, None),
        (1, True, None),
        (3, True, None),
    ],
)
def test_who_speaks_next(said: int, ended: bool, speaker: str | None) -> None:
    assert next_speaker(("Asker", "Asked"), said, ended) == speaker


def test_named_keeps_only_allowed_names_each_once_in_order() -> None:
    assert named(["B", "B", "Z", "A", "C"], ["A", "B"]) == ("B", "A")


@pytest.mark.parametrize(
    ("activity", "partners", "carried_out"),
    [
        pytest.param(
            "talk",
            ["B", "Z", "C", "D", "E"],
            ("talk", ["B", "C", "D"]),
            id="at most three, all real",
        ),
        pytest.param("talk", ["Z", "A"], ("wander", []), id="talking to nobody is wandering"),
        pytest.param("wander", ["B"], ("wander", []), id="only talkers keep partners"),
        pytest.param("chore", [], ("chore", []), id="a chore stays a chore"),
    ],
)
def test_an_intent_as_the_town_carries_it_out(
    activity: str, partners: list[str], carried_out: tuple[str, list[str]]
) -> None:
    intent = DuskIntent.model_validate({"activity": activity, "partners": partners, "topic": "t"})

    result = settled(intent, ["B", "C", "D", "E"])

    assert (result.activity, result.partners) == carried_out


def test_the_partner_of_either_resident_is_the_other() -> None:
    assert (partner_of(("A", "B"), "A"), partner_of(("A", "B"), "B")) == ("B", "A")


def test_everyone_sees_a_meeting_in_seat_order_whoever_asked() -> None:
    living = ["Ava", "Bram", "Cora"]

    assert as_seen(("Cora", "Ava"), living) == as_seen(("Ava", "Cora"), living) == ("Ava", "Cora")
