"""The game runner: plays a whole game from casting to the final verdict."""

import asyncio
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass, replace
from random import Random

from mm.agents import Brain, BrainFactory
from mm.engine import GameConfig, Phase
from mm.engine.casting import cast
from mm.engine.decisions import Decision, DecisionRequest
from mm.engine.events import DecisionFellBack, Event, EventPayload, GameEnded, PhaseStarted
from mm.engine.perception import perceived_by
from mm.engine.rules import Verdict, verdict, verdict_at_end_of_day, why_illegal
from mm.engine.state import GameState
from mm.orchestrator.log import EventLog, EventObserver
from mm.orchestrator.phases.dawn import run_dawn
from mm.orchestrator.phases.discussion import run_discussion
from mm.orchestrator.phases.reflection import run_reflections
from mm.orchestrator.phases.vote import run_vote

Step = Callable[["Game"], Awaitable[None]]

DAY: tuple[Step, ...] = (run_dawn, run_reflections, run_discussion, run_vote, run_reflections)
"""One Day: a Phase or a round of reflections per step, with a win check after each."""


class IllegalDecisionError(Exception):
    """A decision source answered with something the rules do not allow."""


@dataclass(frozen=True)
class Decided[D: Decision]:
    """A decision the game received, with the request it answered."""

    request: DecisionRequest
    decision: D
    fallback_reason: str | None = None


@dataclass(frozen=True)
class GameResult:
    events: list[Event]
    state: GameState


class Game:
    def __init__(
        self, config: GameConfig, brain_for: BrainFactory, observers: Sequence[EventObserver] = ()
    ) -> None:
        self.config = config
        self.rng = Random(config.seed)
        self.log = EventLog(observers)
        self.brain_for = brain_for
        self.brains: dict[str, Brain] = {}
        self._decisions_asked = 0
        self._fallbacks_reported: set[str] = set()

    @property
    def state(self) -> GameState:
        return self.log.state

    async def play(self) -> None:
        for payload in cast(self.config, self.rng):
            await self.append(payload)
        self.brains = {resident.name: self.brain_for(resident) for resident in self.state.residents}
        while True:
            for step in DAY:
                await step(self)
                if outcome := verdict(self.state):
                    return await self.end(outcome)
            if outcome := verdict_at_end_of_day(self.state):
                return await self.end(outcome)

    async def end(self, outcome: Verdict) -> None:
        await self.append(GameEnded(winner=outcome.winner, reason=outcome.reason))

    async def append(self, payload: EventPayload, cause: Decided[Decision] | None = None) -> Event:
        """Append an event; if a decision caused it, link them and report a fallback once."""
        if cause is None:
            return await self.log.append(payload)
        event = await self.log.append(payload, decision_id=cause.request.id)
        if cause.fallback_reason and cause.request.id not in self._fallbacks_reported:
            self._fallbacks_reported.add(cause.request.id)
            fell_back = DecisionFellBack(
                resident=cause.request.resident,
                kind=cause.request.kind,
                reason=cause.fallback_reason,
            )
            await self.log.append(fell_back, decision_id=cause.request.id)
        return event

    async def start_phase(self, phase: Phase) -> None:
        day = self.state.day + 1 if phase is Phase.DAWN else self.state.day
        await self.append(PhaseStarted(day=day, phase=phase))

    async def decide[D: Decision](self, request: DecisionRequest, answer: type[D]) -> Decided[D]:
        """Ask one Resident's decision source, showing it only what that Resident perceives."""
        return await self._ask(self._stamp(request), answer)

    async def decide_all[D: Decision](
        self, requests: Sequence[DecisionRequest], answer: type[D]
    ) -> list[Decided[D]]:
        """Ask several Residents at once. Answers come back in the order they were asked."""
        stamped = [self._stamp(request) for request in requests]
        return list(await asyncio.gather(*(self._ask(request, answer) for request in stamped)))

    def _stamp(self, request: DecisionRequest) -> DecisionRequest:
        self._decisions_asked += 1
        return replace(request, id=f"d{self._decisions_asked}")

    async def _ask[D: Decision](self, request: DecisionRequest, answer: type[D]) -> Decided[D]:
        view = perceived_by(self.log.events, request.resident)
        reply = await self.brains[request.resident].decide(request, view)
        decision = reply.decision
        if not isinstance(decision, answer):
            raise IllegalDecisionError(f"{request} was answered with {decision!r}")
        if problem := why_illegal(request, decision):
            raise IllegalDecisionError(f"{request.resident}'s {request.kind}: {problem}")
        return Decided(request=request, decision=decision, fallback_reason=reply.fallback_reason)


async def play_game(
    config: GameConfig, brain_for: BrainFactory, observers: Sequence[EventObserver] = ()
) -> GameResult:
    """Play one whole game. Observers hear every event as it is appended."""
    game = Game(config, brain_for, observers)
    await game.play()
    return GameResult(events=game.log.events, state=game.state)
