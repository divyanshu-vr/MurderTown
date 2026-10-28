"""Scripted bots: rule-based Residents that need no language model.

They make games instant and free, which is what rules tests and demos need.
They play legally but naively: Town bots vote at random, Murderer bots at
random among everyone except their teammates, and a scripted Sheriff fires now
and then at a random Resident. In their reflections they suspect whoever they
have accused. Now and then a bot loses its train of thought and falls back to
the safe default, as an Agent sometimes does, so recorded games show fallbacks.
"""

from collections.abc import Sequence
from random import Random

from mm.agents.answers import ANSWERS
from mm.agents.brain import Brain, BrainFactory
from mm.engine import Resident, Role
from mm.engine.decisions import (
    Answer,
    Ballot,
    Bid,
    Decision,
    DecisionKind,
    DecisionRequest,
    LastWords,
    Reflection,
    Showdown,
    Statement,
    Suspicion,
)
from mm.engine.events import Event, StatementMade
from mm.engine.state import GameState

OPENING_LINES = (
    "Hello, I'm {me}. Keep your eyes open, everyone.",
    "I'm {me}. Someone in this square is not who they seem.",
    "{me} here. Let's stay calm and think this through.",
    "I'm {me}, and I intend to survive this. Who's with me?",
)

QUIET_BIDS = (0, 0, 0, 1, 1, 2, 3)
"""Mostly listening, sometimes wanting a word."""

SHERIFF_FIRES_ONE_DAY_IN = 5

LAPSE_ONE_DECISION_IN = 40
"""How rarely a bot loses its train of thought and falls back to the safe default."""


class ScriptedBot:
    def __init__(self, rng: Random, *, lapses: bool = True) -> None:
        self.rng, self.lapses = rng, lapses

    async def decide(self, request: DecisionRequest, view: Sequence[Event]) -> Answer:
        if self.lapses and self.rng.randrange(LAPSE_ONE_DECISION_IN) == 0:
            return Answer(ANSWERS[request.kind].fallback, fallback_reason="lost the thread")
        return Answer(self._decision(request, view))

    def _decision(self, request: DecisionRequest, view: Sequence[Event]) -> Decision:
        me = request.resident
        match request.kind:
            case DecisionKind.STATEMENT:
                return self._statement(request, GameState.fold(view))
            case DecisionKind.BID:
                urgency = 4 if _addressed_last(view, me) else self.rng.choice(QUIET_BIDS)
                return Bid(urgency=urgency, reason="a hunch")
            case DecisionKind.SHOWDOWN:
                if self.rng.randrange(SHERIFF_FIRES_ONE_DAY_IN) == 0:
                    target = self.rng.choice(request.options)
                    return Showdown(fire=True, target=target, reason="a hunch")
                return Showdown(fire=False, target=None, reason="not yet")
            case DecisionKind.BALLOT:
                return Ballot(choice=self.rng.choice(self._ballot_options(request, view)))
            case DecisionKind.LAST_WORDS:
                return LastWords(text="Remember what I told you.")
            case DecisionKind.REFLECTION:
                return self._reflection(request, view)

    def _statement(self, request: DecisionRequest, known: GameState) -> Statement:
        me = request.resident
        if request.part == "opening_round":
            return Statement.plain(self.rng.choice(OPENING_LINES).format(me=me))
        doubted = self.rng.choice([name for name in known.living if name != me])
        return Statement(
            text=f"I have my doubts about {doubted}.",
            addressed=[doubted],
            accused=[doubted],
            defended=[],
            claimed_role=None,
        )

    def _reflection(self, request: DecisionRequest, view: Sequence[Event]) -> Reflection:
        day = GameState.fold(view).day
        doubted = [name for name in _accused_by(view, request.resident) if name in request.options]
        suspicions = [
            Suspicion(resident=name, suspicion=self.rng.randint(55, 90), note="I said I doubt them")
            for name in doubted
        ]
        plan = f"I doubt {', '.join(doubted)}." if doubted else "Watch who votes with whom."
        return Reflection(
            journal_entry=f"Still wary of {doubted[-1]}." if doubted else "Nothing certain yet.",
            notebook=f"As of Day {day}: {plan}",
            suspicions=suspicions,
        )

    def _ballot_options(self, request: DecisionRequest, view: Sequence[Event]) -> list[str]:
        known = GameState.fold(view)
        if known.roles.get(request.resident) is not Role.MURDERER:
            return list(request.options)
        return [
            option for option in request.options if known.roles.get(option) is not Role.MURDERER
        ]


def _addressed_last(view: Sequence[Event], me: str) -> bool:
    """Whether the latest Statement spoke to this Resident by name."""
    statements = [event.payload for event in view if isinstance(event.payload, StatementMade)]
    return bool(statements) and me in statements[-1].addressed


def _accused_by(view: Sequence[Event], me: str) -> list[str]:
    """Everyone this Resident has accused in a Statement, each once, in the order accused."""
    accused = [
        name
        for event in view
        if isinstance(event.payload, StatementMade) and event.payload.speaker == me
        for name in event.payload.accused
    ]
    return list(dict.fromkeys(accused))


def scripted_bots(seed: int) -> BrainFactory:
    """A factory giving every Resident its own deterministic bot."""

    def make(resident: Resident) -> Brain:
        return ScriptedBot(Random(f"{seed}:{resident.name}"))

    return make
