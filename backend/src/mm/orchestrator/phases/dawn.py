"""Dawn: a new Day begins with the Night's news, the narrator's recap, then reflection.

Dawn announces the Night's murder, or that the Doctor saved the Victim. If that
death decides the game, nobody says anything more. The first Dawn follows no
Night, so it has no news and no recap.
"""

from typing import TYPE_CHECKING

from mm.engine import Phase
from mm.engine.decisions import DecisionKind, DecisionRequest, Recap
from mm.engine.events import RecapNarrated
from mm.engine.night import dawn_news
from mm.engine.rules import trimmed
from mm.orchestrator.narrator import NARRATOR
from mm.orchestrator.phases.reflection import reflect

if TYPE_CHECKING:
    from mm.orchestrator.game import Game


async def run_dawn(game: "Game") -> None:
    await game.start_phase(Phase.DAWN)
    if game.state.day == 1:
        await reflect(game)
        return
    for news in dawn_news(game.state):
        await game.append(news)
    if game.decided:
        return
    told = await game.decide(DecisionRequest(DecisionKind.RECAP, NARRATOR.name), Recap)
    await game.append(RecapNarrated(text=trimmed(told.decision.text)), cause=told)
    await reflect(game)
