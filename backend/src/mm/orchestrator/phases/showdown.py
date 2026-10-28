"""Showdown: while an armed Sheriff lives, they may fire their single bullet in public.

The Phase only happens while the Sheriff could shoot. Deaths reveal roles and
shots are public, so its absence tells the town nothing it did not know.
"""

from typing import TYPE_CHECKING

from mm.engine import Phase
from mm.engine.decisions import DecisionKind, DecisionRequest, Showdown
from mm.engine.events import SheriffHeldFire
from mm.engine.showdown import armed_sheriff, shot_events, shot_options

if TYPE_CHECKING:
    from mm.orchestrator.game import Game


async def run_showdown(game: "Game") -> None:
    if game.config.sheriff_shoots_at != "showdown":
        return
    if sheriff := armed_sheriff(game.state):
        await game.start_phase(Phase.SHOWDOWN)
        await sheriff_decides(game, sheriff)


async def sheriff_decides(game: "Game", sheriff: str) -> None:
    """Ask the Sheriff to hold or fire, and carry out a shot. Night uses this too."""
    request = DecisionRequest(DecisionKind.SHOWDOWN, sheriff, shot_options(game.state, sheriff))
    choice = await game.decide(request, Showdown)
    target = choice.decision.target
    if not (choice.decision.fire and target):
        await game.append(SheriffHeldFire(sheriff=sheriff), cause=choice)
        return
    shot, *deaths = shot_events(game.state, sheriff, target)
    await game.append(shot, cause=choice)
    for death in deaths:
        await game.append(death)
