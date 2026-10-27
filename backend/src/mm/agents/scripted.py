"""Scripted bots: rule-based Residents that need no language model.

They make games instant and free, which is what rules tests and demos need.
They play legally but naively: Town bots vote at random, and Murderer bots at
random among everyone except their teammates.
"""

from collections.abc import Sequence
from random import Random

from mm.agents.brain import Brain, BrainFactory
from mm.engine import Resident, Role
from mm.engine.decisions import Ballot, Decision, DecisionKind, DecisionRequest, Statement
from mm.engine.events import Event
from mm.engine.state import GameState

OPENING_LINES = (
    "Hello, I'm {me}. Keep your eyes open, everyone.",
    "I'm {me}. Someone in this square is not who they seem.",
    "{me} here. Let's stay calm and think this through.",
    "I'm {me}, and I intend to survive this. Who's with me?",
)


class ScriptedBot:
    def __init__(self, rng: Random) -> None:
        self.rng = rng

    async def decide(self, request: DecisionRequest, view: Sequence[Event]) -> Decision:
        match request.kind:
            case DecisionKind.STATEMENT:
                return Statement(text=self.rng.choice(OPENING_LINES).format(me=request.resident))
            case DecisionKind.BALLOT:
                return Ballot(choice=self.rng.choice(self._ballot_options(request, view)))

    def _ballot_options(self, request: DecisionRequest, view: Sequence[Event]) -> list[str]:
        known = GameState.fold(view)
        if known.roles.get(request.resident) is not Role.MURDERER:
            return list(request.options)
        return [
            option for option in request.options if known.roles.get(option) is not Role.MURDERER
        ]


def scripted_bots(seed: int) -> BrainFactory:
    """A factory giving every Resident its own deterministic bot."""

    def make(resident: Resident) -> Brain:
        return ScriptedBot(Random(f"{seed}:{resident.name}"))

    return make
