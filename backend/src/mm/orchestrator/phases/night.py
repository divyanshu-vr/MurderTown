"""Night: the town sleeps. If the game is set up that way, this is when the Sheriff may shoot."""

from typing import TYPE_CHECKING

from mm.engine import Phase
from mm.engine.showdown import armed_sheriff
from mm.orchestrator.phases.showdown import sheriff_decides

if TYPE_CHECKING:
    from mm.orchestrator.game import Game


async def run_night(game: "Game") -> None:
    await game.start_phase(Phase.NIGHT)
    if game.config.sheriff_shoots_at == "night" and (sheriff := armed_sheriff(game.state)):
        await sheriff_decides(game, sheriff)
