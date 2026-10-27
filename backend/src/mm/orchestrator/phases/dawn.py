"""Dawn: a new Day begins, and Residents reflect on what the Night brought."""

from typing import TYPE_CHECKING

from mm.engine import Phase
from mm.orchestrator.phases.reflection import reflect

if TYPE_CHECKING:
    from mm.orchestrator.game import Game


async def run_dawn(game: "Game") -> None:
    await game.start_phase(Phase.DAWN)
    await reflect(game)
