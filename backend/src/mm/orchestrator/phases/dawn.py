"""Dawn: a new Day begins with the Night's news, the narrator's recap, then reflection.

Dawn announces the Night's murder, or that the Doctor saved the Victim. If that
death decides the game, nobody says anything more. The game opens with a Night,
so even the first Dawn, Day 2's, has news to tell.
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
    for news in dawn_news(game.state):
        await game.append(news)
    if game.decided:
        return
    told = await game.decide(DecisionRequest(DecisionKind.RECAP, NARRATOR.name), Recap)
    await game.append(RecapNarrated(text=trimmed(told.decision.text)), cause=told)
    await reflect(game)
