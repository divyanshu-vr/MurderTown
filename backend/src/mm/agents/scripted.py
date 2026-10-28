"""Scripted bots: rule-based Residents that need no language model.

They make games instant and free, which is what rules tests and demos need.
They play legally but naively: Town bots vote at random, Murderer bots at
random among everyone except their teammates, and a scripted Sheriff fires now
and then at a random Resident. At Night, Murderer bots each propose a random
Victim and then vote for the most proposed; the Doctor and Detective choose at
random. In their reflections they suspect whoever they have accused. Now and
then a bot loses its train of thought and falls back to the safe default, as an
Agent sometimes does, so recorded games show fallbacks.
"""

from collections.abc import Sequence
from random import Random

from mm.agents.answers import ANSWERS
from mm.agents.brain import Brain, BrainFactory
from mm.engine import Resident, Role
from mm.engine.decisions import (
    Answer,
    Bid,
    ConversationMessage,
    Decision,
    DecisionKind,
    DecisionRequest,
    DenMessage,
    DuskIntent,
    LastWords,
    Recap,
    Reflection,
    Showdown,
    Statement,
    Suspicion,
    Target,
)
from mm.engine.dusk import PARTNERS_NAMED_AT_MOST
from mm.engine.events import (
    AttackThwarted,
    DenMessagePosted,
    Event,
    ResidentDied,
    StatementMade,
)
from mm.engine.perception import began, since_last
from mm.engine.phases import Phase
from mm.engine.state import GameState
from mm.engine.tally import plurality

OPENING_LINES = (
    "Hello, I'm {me}. Keep your eyes open, everyone.",
    "I'm {me}. Someone in this square is not who they seem.",
    "{me} here. Let's stay calm and think this through.",
    "I'm {me}, and I intend to survive this. Who's with me?",
)

QUIET_BIDS = (0, 0, 0, 1, 1, 2, 3)
"""Mostly listening, sometimes wanting a word."""

SHERIFF_FIRES_ONE_DAY_IN = 5

TALKS_AT_DUSK = 0.5
"""How often a bot asks for a Conversation rather than wandering or doing a chore."""

ENDS_ONE_MESSAGE_IN = 3
"""How often a bot ends a Conversation with the message it is saying."""

LAPSE_ONE_DECISION_IN = 40
"""How rarely a bot loses its train of thought and falls back to the safe default."""


class ScriptedBot:
    def __init__(self, rng: Random, *, lapses: bool = True) -> None:
        self.rng, self.lapses = rng, lapses

    async def decide(self, request: DecisionRequest, view: Sequence[Event]) -> Answer:
        if self.lapses and self.rng.randrange(LAPSE_ONE_DECISION_IN) == 0:
            fallback = ANSWERS[request.kind].fallback(request, self.rng)
            return Answer(fallback, fallback_reason="lost the thread")
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
                choice = self.rng.choice(self._ballot_options(request, view))
                return Target(target=choice, reason="a hunch")
            case DecisionKind.LAST_WORDS:
                return LastWords(text="Remember what I told you.")
            case DecisionKind.REFLECTION:
                return self._reflection(request, view)
            case (
                DecisionKind.DEN_MESSAGE
                | DecisionKind.KILL_VOTE
                | DecisionKind.PROTECT
                | DecisionKind.INVESTIGATE
                | DecisionKind.RECAP
            ):
                return self._night_decision(request, view)
            case DecisionKind.DUSK_INTENT | DecisionKind.CONVERSATION_MESSAGE:
                return self._dusk_decision(request, view)

    def _dusk_decision(self, request: DecisionRequest, view: Sequence[Event]) -> Decision:
        """Half the bots seek out one to three others; Conversations end at random."""
        if request.kind is DecisionKind.DUSK_INTENT:
            if self.rng.random() < TALKS_AT_DUSK:
                wanted = min(len(request.options), self.rng.randint(1, PARTNERS_NAMED_AT_MOST))
                partners = self.rng.sample(request.options, wanted)
                return DuskIntent(activity="talk", partners=partners, topic="whom to trust")
            return DuskIntent(activity=self.rng.choice(["wander", "chore"]), partners=[], topic="")
        doubted = self._someone_else(GameState.fold(view), request.resident)
        ending = self.rng.randrange(ENDS_ONE_MESSAGE_IN) == 0
        return ConversationMessage(text=f"I don't trust {doubted}.", end_conversation=ending)

    def _someone_else(self, known: GameState, me: str) -> str:
        """A random living Resident other than this one."""
        return self.rng.choice(known.others_living(me))

    def _night_decision(self, request: DecisionRequest, view: Sequence[Event]) -> Decision:
        match request.kind:
            case DecisionKind.DEN_MESSAGE:
                victim = self.rng.choice(request.options)
                return DenMessage(text=f"Let's take {victim} tonight.", proposed_victim=victim)
            case DecisionKind.KILL_VOTE:
                options = request.options
                proposed = [v for v in _proposed_tonight(view) if v in options]
                victim = plurality(proposed, self.rng) if proposed else self.rng.choice(options)
                return Target(target=victim, reason="as the Den agreed")
            case DecisionKind.PROTECT | DecisionKind.INVESTIGATE:
                return Target(target=self.rng.choice(request.options), reason="a hunch")
            case DecisionKind.RECAP:
                return Recap(text=_recap(view))
        raise ValueError(f"{request.kind} is not decided at Night or Dawn")

    def _statement(self, request: DecisionRequest, known: GameState) -> Statement:
        me = request.resident
        if request.part == "opening_round":
            return Statement.plain(self.rng.choice(OPENING_LINES).format(me=me))
        doubted = self._someone_else(known, me)
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


def _proposed_tonight(view: Sequence[Event]) -> list[str]:
    """The Victims proposed in the Den since Night fell."""
    tonight = since_last(view, began(Phase.NIGHT))
    return [
        event.payload.proposed_victim
        for event in tonight
        if isinstance(event.payload, DenMessagePosted) and event.payload.proposed_victim
    ]


def _recap(view: Sequence[Event]) -> str:
    """The narrator's line for this Dawn: who was found dead, or who survived an attack."""
    day = GameState.fold(view).day
    for event in since_last(view, began(Phase.DAWN)):
        match event.payload:
            case ResidentDied(resident=victim, cause="murdered"):
                return f"Day {day} dawns, and the town finds {victim} dead."
            case AttackThwarted(saved=saved):
                return f"Day {day} dawns. {saved or 'Someone'} was attacked, and lived."
    return f"Day {day} dawns quietly over the town."


def scripted_bots(seed: int) -> BrainFactory:
    """A factory giving every Resident its own deterministic bot."""

    def make(resident: Resident) -> Brain:
        return ScriptedBot(Random(f"{seed}:{resident.name}"))

    return make
