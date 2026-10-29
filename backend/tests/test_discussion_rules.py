"""Table tests for who speaks next on the Open floor: a Right of reply, then the Bids, then
waiting; and whom a Statement addresses and asks, as the game records it.

Each row of `test_who_speaks_next` starts from an Opening round of A, B, C and D, in that
order, so A has waited longest, then any `then` Statements on the Open floor, and asks who
makes the next Statement given the Bids.
"""

from collections.abc import Sequence

import pytest

from mm.engine.decisions import StatementPart
from mm.engine.discussion import Floor, addressing
from mm.engine.events import StatementMade

OPENING_ROUND = ("A", "B", "C", "D")


def said(
    speaker: str,
    addressed: Sequence[str] = (),
    asked: str | None = None,
    part: StatementPart = "open_floor",
    answering: bool = False,
) -> StatementMade:
    """A Statement as the game records it: whom it asks, it also addresses."""
    named = (*addressed, asked) if asked and asked not in addressed else tuple(addressed)
    return StatementMade(
        speaker=speaker, text="...", part=part, addressed=named, asked=asked, answering=answering
    )


def answer(speaker: str, addressed: Sequence[str] = (), asked: str | None = None) -> StatementMade:
    """A Statement made by Right of reply or a 4 that counted."""
    return said(speaker, addressed, asked, answering=True)


def opening(*statements: StatementMade) -> list[StatementMade]:
    return [*(said(speaker, part="opening_round") for speaker in OPENING_ROUND), *statements]


@pytest.mark.parametrize(
    ("then", "bids", "speaker"),
    [
        pytest.param([], {"C": 2, "D": 3}, "D", id="the highest Bid speaks"),
        pytest.param([], {"B": 3, "D": 3}, "B", id="equal Bids go to whoever waited longest"),
        pytest.param(
            [said("B")], {"A": 2, "B": 2}, "A", id="speaking again puts a Resident back in line"
        ),
        pytest.param([], {"A": 0, "B": 0}, None, id="nobody speaks when every Bid is 0"),
        pytest.param([], {}, None, id="nobody speaks when nobody Bids"),
        pytest.param(
            [said("D", asked="C")], {"A": 3, "C": 1}, "C", id="the one asked answers next"
        ),
        pytest.param(
            [said("D", asked="C")], {"A": 3, "C": 0}, "A", id="the one asked may decline with 0"
        ),
        pytest.param(
            [said("D", asked="C"), answer("C"), said("A", asked="C")],
            {"B": 3, "C": 1},
            "B",
            id="a Resident has a Right of reply once per Open floor",
        ),
        pytest.param(
            [said("D", asked="C"), said("A", asked="B")],
            {"B": 1, "D": 3},
            "B",
            id="each Resident has their own Right of reply",
        ),
        pytest.param(
            [said("D", asked="C"), said("A")],
            {"B": 3, "C": 1},
            "B",
            id="only the last Statement's question gets a reply",
        ),
        pytest.param(
            [said("A"), said("D", asked="C"), answer("C", asked="A")],
            {"A": 1, "B": 3},
            "B",
            id="a question asked in an answer waits for the Bids",
        ),
        pytest.param(
            [said("C", addressed=["D"]), said("D", addressed=["C"])],
            {"A": 3, "C": 4},
            "C",
            id="a Statement that won on the Bids is no answer, however it names its speaker",
        ),
        pytest.param([], {"A": 3, "D": 4}, "A", id="a 4 nobody asked for counts as 3"),
        pytest.param(
            [said("C", addressed=["D"])], {"A": 3, "D": 4}, "D", id="a 4 from the addressed counts"
        ),
        pytest.param(
            [said("C", addressed=["B"])],
            {"A": 3, "D": 4},
            "A",
            id="a 4 counts only for whom the Statement named",
        ),
        pytest.param(
            [said("C", addressed=["D"]), answer("D", addressed=["C"])],
            {"A": 3, "C": 4},
            "A",
            id="a 4 from whom an answer addressed counts as 3",
        ),
        pytest.param(
            [said("C"), said("A", addressed=["B", "C"]), answer("B", addressed=["A", "C"])],
            {"C": 4, "D": 3},
            "D",
            id="three cannot keep the floor by answering one another",
        ),
    ],
)
def test_who_speaks_next(
    then: list[StatementMade], bids: dict[str, int], speaker: str | None
) -> None:
    assert Floor.of(opening(*then)).next_speaker(bids) == speaker


def test_a_question_in_the_opening_round_does_not_use_up_a_right_of_reply() -> None:
    statements = [
        said("A", asked="B", part="opening_round"),
        said("B", part="opening_round"),
        said("C", part="opening_round"),
        said("D", asked="B"),
    ]

    assert Floor.of(statements).next_speaker({"A": 3, "B": 1}) == "B"


def test_the_last_opening_statements_question_is_answered_first() -> None:
    statements = [*opening()[:-1], said("D", asked="A", part="opening_round")]

    assert Floor.of(statements).next_speaker({"A": 1, "B": 3}) == "A"


def test_a_resident_who_never_spoke_has_waited_longest_and_seat_order_breaks_the_rest() -> None:
    assert Floor.of(opening()).next_speaker({"E": 2, "F": 2, "A": 2}) == "E"


@pytest.mark.parametrize(
    ("then", "speaker", "bid", "answering"),
    [
        pytest.param([said("D", asked="C")], "C", 1, True, id="speaking by Right of reply"),
        pytest.param([said("D", addressed=["C"])], "C", 4, True, id="speaking on a 4 that counts"),
        pytest.param([said("D", addressed=["C"])], "C", 3, False, id="speaking on a 3"),
        pytest.param([said("D")], "C", 4, False, id="speaking on a 4 that counts as 3"),
    ],
)
def test_which_statements_are_answers(
    then: list[StatementMade], speaker: str, bid: int, answering: bool
) -> None:
    assert Floor.of(opening(*then)).answers(speaker, bid) is answering


OTHERS = ("Bo", "Cy", "Di")
"""Everyone but the speaker; Di is dead."""
LIVING = ("Bo", "Cy")


@pytest.mark.parametrize(
    ("addressed", "asked", "recorded"),
    [
        pytest.param(["Bo"], "Cy", (("Bo", "Cy"), "Cy"), id="whom it asks it also addresses"),
        pytest.param(["Cy", "Cy"], "Cy", (("Cy",), "Cy"), id="each named once"),
        pytest.param(["Bo"], "Di", (("Bo",), None), id="it cannot ask the dead"),
        pytest.param(["Bo"], "Al", (("Bo",), None), id="it cannot ask its own speaker"),
        pytest.param(["Zed", "Di"], None, (("Di",), None), id="it addresses real Residents only"),
    ],
)
def test_whom_a_statement_addresses_and_asks(
    addressed: list[str], asked: str | None, recorded: tuple[tuple[str, ...], str | None]
) -> None:
    assert addressing(addressed, asked, OTHERS, LIVING) == recorded
