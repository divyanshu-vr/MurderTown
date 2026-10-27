"""Reflections: Residents write private notes to their future selves.

They run after Dawn and after the Vote. A Resident with no news since their last
reflection skips it, so a quiet stretch costs nothing.
"""

from typing import TYPE_CHECKING

from mm.engine.decisions import DecisionKind, DecisionRequest, Reflection
from mm.engine.events import ReflectionWritten
from mm.engine.perception import has_news, perceived_by

if TYPE_CHECKING:
    from mm.orchestrator.game import Game


async def run_reflections(game: "Game") -> None:
    writers = [
        name for name in game.state.living if has_news(perceived_by(game.log.events, name), name)
    ]
    requests = [DecisionRequest(DecisionKind.REFLECTION, name) for name in writers]
    others = {resident.name for resident in game.state.residents}

    for decided in await game.decide_all(requests, Reflection):
        writer, reflection = decided.request.resident, decided.decision
        written = ReflectionWritten(
            resident=writer,
            journal_entry=reflection.journal_entry,
            notebook=reflection.notebook,
            suspicions=tuple(s for s in reflection.suspicions if s.resident in others - {writer}),
        )
        await game.append(written, cause=decided)
