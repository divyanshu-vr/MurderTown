"""The transcript `mm play` prints: how a Statement reads, with whom it asks to answer."""

from mm.cli.transcript import describe
from mm.engine import Phase
from mm.engine.events import Event, StatementMade, Visibility


def statement(asked: str | None) -> Event:
    said = StatementMade(speaker="Otto", text="Where were you?", part="open_floor", asked=asked)
    return Event(
        seq=1, day=2, phase=Phase.DISCUSSION, visibility=Visibility.everyone(), payload=said
    )


def test_a_statement_reads_as_its_words_and_whom_it_asks_to_answer() -> None:
    assert describe(statement("Zane")) == 'Otto: "Where were you?" (asks Zane to answer)'
    assert describe(statement(None)) == 'Otto: "Where were you?"'
