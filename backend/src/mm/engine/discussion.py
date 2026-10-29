"""Rules of Discussion: who speaks next on the Open floor, and when the Open floor is over.

On the Open floor every living Resident Bids how urgently they want to speak.

- Right of reply: a Statement may ask one Resident to answer. If they Bid above 0, they
  make the next Statement. Each Resident answers by Right of reply once per Open floor.
- Otherwise the highest Bid speaks. A 4 says the last Statement addressed you, so it counts
  as 3 from anyone else.
- An answer does not start another: a Statement made by Right of reply or a 4 that
  counted is an answer, and it gives nobody a Right of reply or a 4 that counts. So answers
  and open Turns alternate, and questions cannot keep the floor from the Bids.
- Among equal Bids, whoever has waited longest since their own last Statement speaks.
  Everyone speaks in the Opening round, so waiting always settles it.

If every Bid is 0, nobody speaks that Turn.
"""

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Literal, Self

from mm.engine.config import GameConfig
from mm.engine.events import StatementMade
from mm.engine.rules import named

ADDRESSED_BID = 4
"""The Bid that says the last Statement addressed you and you must respond."""


@dataclass(frozen=True)
class Floor:
    """The Discussion so far, as the Open floor needs it: every Statement's speaker in order,
    the last Statement, and who has already answered by Right of reply. A fold of the Day's
    Statements, so the game and a Resident's prompt read it the same way."""

    spoken: tuple[str, ...] = ()
    last: StatementMade | None = None
    replied: frozenset[str] = frozenset()

    @classmethod
    def of(cls, statements: Iterable[StatementMade]) -> Self:
        floor = cls()
        for statement in statements:
            floor = floor.after(statement)
        return floor

    @property
    def may_reply(self) -> str | None:
        """Whom the last Statement asked to answer, if they have a Right of reply."""
        if self.last is None or self.last.answering or self.last.asked in self.replied:
            return None
        return self.last.asked

    def addressed(self, resident: str) -> bool:
        """Whether a 4 from the Resident counts: the last Statement addressed them, and was
        not itself an answer."""
        last = self.last
        return last is not None and resident in last.addressed and not last.answering

    def answers(self, speaker: str, bid: int) -> bool:
        """Whether the next Statement, by `speaker` on that Bid, is an answer: made by Right of
        reply or a 4 that counted."""
        return speaker == self.may_reply or self.counted(speaker, bid) == ADDRESSED_BID

    def after(self, statement: StatementMade) -> Self:
        """The Floor once `statement` is made. Only the Open floor uses up a Right of reply."""
        replying = statement.part == "open_floor" and statement.speaker == self.may_reply
        return type(self)(
            spoken=(*self.spoken, statement.speaker),
            last=statement,
            replied=(self.replied | {statement.speaker}) if replying else self.replied,
        )

    def counted(self, resident: str, bid: int) -> int:
        """A Bid as it counts: a 4 counts as 3 unless the Resident was addressed."""
        if bid >= ADDRESSED_BID and not self.addressed(resident):
            return ADDRESSED_BID - 1
        return bid

    def next_speaker(self, bids: Mapping[str, int]) -> str | None:
        """Who makes the next Statement, given each Resident's Bid; None if nobody wants to.
        Among those who never spoke, the order of `bids` (seat order) decides."""
        asked = self.may_reply
        if asked is not None and bids.get(asked, 0) > 0:
            return asked
        counted = {name: self.counted(name, bid) for name, bid in bids.items()}
        top = max(counted.values(), default=0)
        if top == 0:
            return None
        last_spoke = {name: position for position, name in enumerate(self.spoken)}
        eager = [name for name, bid in counted.items() if bid == top]
        return min(eager, key=lambda name: last_spoke.get(name, -1))


def addressing(
    addressed: Iterable[str], asked: str | None, others: Iterable[str], living: Iterable[str]
) -> tuple[tuple[str, ...], str | None]:
    """Whom a Statement addresses and asks, as the game records them: only other Residents,
    each once; only a living one asked, who is then among those addressed too."""
    asked = asked if asked in set(living) else None
    return named([*addressed, *([asked] if asked else [])], others), asked


QUIET_TURNS_TO_END = 2
"""The Open floor ends after this many Turns in a row in which nobody wanted to speak."""


OpenFloorLimit = Literal["statements", "quiet", "time"]


def open_floor_limit(
    config: GameConfig, statements_made: int, quiet_turns: int, out_of_time: bool
) -> OpenFloorLimit | None:
    """Which of its three limits ended the Open floor, or None while it goes on. Whether
    its time is up is for the caller to say: the engine reads no clock."""
    if statements_made >= config.open_floor_statements:
        return "statements"
    if quiet_turns >= QUIET_TURNS_TO_END:
        return "quiet"
    return "time" if out_of_time else None
