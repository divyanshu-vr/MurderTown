"""Dawn: a new Day begins."""

from typing import TYPE_CHECKING

from mm.engine import Phase

if TYPE_CHECKING:
    from mm.orchestrator.game import Game


async def run_dawn(game: "Game") -> None:
    await game.start_phase(Phase.DAWN)
