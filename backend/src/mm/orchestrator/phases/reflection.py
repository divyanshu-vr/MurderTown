"""Reflection: Residents write private notes to their future selves.

Dawn and the Vote each end with reflection. A Resident with no news since their
last reflection skips it, so a quiet stretch costs nothing, and nobody reflects
once the game is already decided.
"""

from typing import TYPE_CHECKING

from mm.engine.decisions import DecisionKind, DecisionRequest, Reflection
from mm.engine.events import ReflectionWritten
from mm.engine.perception import has_news, perceived_by
from mm.engine.reflection import suspect_options

if TYPE_CHECKING:
    from mm.orchestrator.game import Game


async def reflect(game: "Game") -> None:
    if game.decided:
        return
    requests = [
        DecisionRequest(DecisionKind.REFLECTION, name, suspect_options(game.state, name))
        for name in game.state.living
        if has_news(perceived_by(game.log.events, name), name)
    ]
    for decided in await game.decide_all(requests, Reflection):
        reflection = decided.decision
        written = ReflectionWritten(
            resident=decided.request.resident,
            journal_entry=reflection.journal_entry,
            notebook=reflection.notebook,
            suspicions=tuple(reflection.suspicions),
        )
        await game.append(written, cause=decided)
