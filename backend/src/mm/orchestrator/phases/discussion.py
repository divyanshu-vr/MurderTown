"""Discussion: the public debate in the town square.

The Opening round comes first: every living Resident makes exactly one
Statement, in a random order that changes every Day.
"""

from typing import TYPE_CHECKING

from mm.engine import Phase
from mm.engine.decisions import DecisionKind, DecisionRequest, Statement
from mm.engine.events import StatementMade

if TYPE_CHECKING:
    from mm.orchestrator.game import Game


async def run_discussion(game: "Game") -> None:
    await game.start_phase(Phase.DISCUSSION)
    order = list(game.state.living)
    game.rng.shuffle(order)
    for speaker in order:
        statement = await game.decide(DecisionRequest(DecisionKind.STATEMENT, speaker), Statement)
        await game.append(StatementMade(speaker=speaker, text=statement.text, part="opening_round"))
