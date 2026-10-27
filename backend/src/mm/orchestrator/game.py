"""The game runner: plays a whole game from casting to the final verdict."""

import asyncio
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass
from random import Random
from typing import TypeVar

from mm.agents import Brain, BrainFactory
from mm.engine import GameConfig, Phase
from mm.engine.casting import cast
from mm.engine.decisions import Decision, DecisionRequest
from mm.engine.events import Event, EventPayload, GameEnded, PhaseStarted
from mm.engine.perception import perceived_by
from mm.engine.rules import Verdict, verdict, verdict_at_end_of_day, why_illegal
from mm.engine.state import GameState
from mm.orchestrator.log import EventLog, EventObserver
from mm.orchestrator.phases.dawn import run_dawn
from mm.orchestrator.phases.discussion import run_discussion
from mm.orchestrator.phases.vote import run_vote

PhaseRunner = Callable[["Game"], Awaitable[None]]

DAY: tuple[PhaseRunner, ...] = (run_dawn, run_discussion, run_vote)

D = TypeVar("D", bound=Decision)


class IllegalDecisionError(Exception):
    """A decision source answered with something the rules do not allow."""


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

    @property
    def state(self) -> GameState:
        return self.log.state

    async def play(self) -> None:
        for payload in cast(self.config, self.rng):
            await self.append(payload)
        self.brains = {resident.name: self.brain_for(resident) for resident in self.state.residents}
        while True:
            for run_phase in DAY:
                await run_phase(self)
                if outcome := verdict(self.state):
                    return await self.end(outcome)
            if outcome := verdict_at_end_of_day(self.state):
                return await self.end(outcome)

    async def end(self, outcome: Verdict) -> None:
        await self.append(GameEnded(winner=outcome.winner, reason=outcome.reason))

    async def append(self, payload: EventPayload) -> Event:
        return await self.log.append(payload)

    async def start_phase(self, phase: Phase) -> None:
        day = self.state.day + 1 if phase is Phase.DAWN else self.state.day
        await self.append(PhaseStarted(day=day, phase=phase))

    async def decide(self, request: DecisionRequest, answer: type[D]) -> D:
        """Ask one Resident's decision source, showing it only what that Resident perceives."""
        view = perceived_by(self.log.events, request.resident)
        decision = await self.brains[request.resident].decide(request, view)
        if not isinstance(decision, answer):
            raise IllegalDecisionError(f"{request} was answered with {decision!r}")
        if problem := why_illegal(request, decision):
            raise IllegalDecisionError(f"{request.resident}'s {request.kind}: {problem}")
        return decision

    async def decide_all(self, requests: Sequence[DecisionRequest], answer: type[D]) -> list[D]:
        """Ask several Residents at once. Answers come back in the order they were asked."""
        return list(await asyncio.gather(*(self.decide(request, answer) for request in requests)))


async def play_game(
    config: GameConfig, brain_for: BrainFactory, observers: Sequence[EventObserver] = ()
) -> GameResult:
    """Play one whole game. Observers hear every event as it is appended."""
    game = Game(config, brain_for, observers)
    await game.play()
    return GameResult(events=game.log.events, state=game.state)
