"""The game runner: plays a whole game from casting to the final verdict."""

import asyncio
import time
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass, replace
from random import Random
from uuid import uuid4

import structlog
from structlog.contextvars import bind_contextvars, bound_contextvars

from mm.agents import Brain, BrainFactory, ModelFailureError
from mm.engine import GameConfig, Phase
from mm.engine.casting import cast
from mm.engine.decisions import Decision, DecisionRequest
from mm.engine.events import (
    DecisionFellBack,
    Event,
    EventPayload,
    GameAborted,
    GameEnded,
    PhaseStarted,
)
from mm.engine.perception import perceived_by
from mm.engine.rules import Verdict, verdict, verdict_at_end_of_day, why_illegal
from mm.engine.state import GameState
from mm.observability import tracing
from mm.orchestrator.log import EventLog, EventObserver
from mm.orchestrator.narrator import NARRATOR
from mm.orchestrator.phases.dawn import run_dawn
from mm.orchestrator.phases.discussion import run_discussion
from mm.orchestrator.phases.dusk import run_dusk
from mm.orchestrator.phases.night import run_night
from mm.orchestrator.phases.showdown import run_showdown
from mm.orchestrator.phases.vote import run_vote

logger = structlog.get_logger(__name__)

PhaseRunner = Callable[["Game"], Awaitable[None]]

DAY: tuple[PhaseRunner, ...] = (
    run_dawn,
    run_discussion,
    run_showdown,
    run_vote,
    run_dusk,
    run_night,
)
"""One Day, in order, with a check for a winner after each Phase. A Phase in which
someone dies checks `Game.decided` itself, so nobody acts once the game is won."""


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
        self,
        config: GameConfig,
        brain_for: BrainFactory,
        observers: Sequence[EventObserver] = (),
        clock: Callable[[], float] = time.monotonic,
        game_id: str = "",
    ) -> None:
        self.config = config
        self.clock = clock
        self.game_id = game_id or uuid4().hex
        self.rng = Random(config.seed)
        self.log = EventLog(observers)
        self.brain_for = brain_for
        self.brains: dict[str, Brain] = {}
        self._decisions_asked = 0
        self._fallbacks_reported: set[str] = set()

    @property
    def state(self) -> GameState:
        return self.log.state

    @property
    def decided(self) -> bool:
        """Whether a side has already won, so nobody should be asked anything more."""
        return verdict(self.state) is not None

    async def play(self) -> None:
        with (
            bound_contextvars(game=self.game_id, day=0, phase=Phase.SETUP),
            tracing.in_game(self.game_id, self.config.seed),
        ):
            try:
                await self._play()
            except ModelFailureError as failed:
                await self.abort(failed)

    async def _play(self) -> None:
        for payload in cast(self.config, self.rng):
            await self.append(payload)
        everyone = (*self.state.residents, NARRATOR)
        self.brains = {resident.name: self.brain_for(resident) for resident in everyone}
        while True:
            for run_phase in DAY:
                await run_phase(self)
                if outcome := verdict(self.state):
                    return await self.end(outcome)
            if outcome := verdict_at_end_of_day(self.state):
                return await self.end(outcome)

    async def end(self, outcome: Verdict) -> None:
        await self.append(GameEnded(winner=outcome.winner, reason=outcome.reason))
        logger.info("game ended", winner=outcome.winner, reason=outcome.reason)

    async def abort(self, failed: ModelFailureError) -> None:
        """Stop the game: the model gave no answer to a decision. The abort names that decision,
        so the Mind inspector can explain it."""
        request = failed.request
        aborted = GameAborted(resident=request.resident, kind=request.kind, reason=failed.problem)
        await self.log.append(aborted, decision_id=request.id)
        logger.warning("game aborted", resident=request.resident, reason=failed.problem)

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
            logger.info(
                "decision fell back",
                resident=cause.request.resident,
                kind=cause.request.kind,
                reason=cause.fallback_reason,
            )
        return event

    async def start_phase(self, phase: Phase) -> None:
        day = self.state.day + 1 if phase is Phase.DAWN else self.state.day
        bind_contextvars(day=day, phase=phase)
        await self.append(PhaseStarted(day=day, phase=phase))
        logger.info("phase started")

    async def decide[D: Decision](self, request: DecisionRequest, answer: type[D]) -> Decided[D]:
        """Ask one Resident's decision source, showing it only what that Resident perceives."""
        return await self._ask(self._stamp(request), answer)

    async def decide_all[D: Decision](
        self,
        requests: Sequence[DecisionRequest],
        answer: type[D],
        pending: Sequence[EventPayload] = (),
    ) -> list[Decided[D]]:
        """Ask several Residents at once. Answers come back in the order they were asked.

        If any decision fails, every ask still finishes, and the first failure in the order
        asked is raised, so the same failures always stop the game the same way.
        `pending` is what has been said but not appended yet; each Resident still
        perceives only the part of it their visibility allows.
        """
        stamped = [self._stamp(request) for request in requests]
        heard = [self.log.unlogged(payload) for payload in pending]
        asked = (self._ask(request, answer, heard) for request in stamped)
        answers = await asyncio.gather(*asked, return_exceptions=True)
        if failure := next((a for a in answers if isinstance(a, BaseException)), None):
            raise failure
        return [a for a in answers if not isinstance(a, BaseException)]

    def _trace_labels(self, request: DecisionRequest) -> dict[str, str]:
        """What a decision's trace says about it: who decided what, when, in which role,
        and how far into the log (its sequence number) the game was when they were asked."""
        role = self.state.roles.get(request.resident)
        return {
            tracing.TRACE_NAME: request.kind,
            tracing.USER: request.resident,
            tracing.METADATA + "decision": request.id,
            tracing.METADATA + "sequence": str(len(self.log.events)),
            tracing.METADATA + "day": str(self.state.day),
            tracing.METADATA + "phase": self.state.phase,
            tracing.METADATA + "role": role or "narrator",
        }

    def _stamp(self, request: DecisionRequest) -> DecisionRequest:
        self._decisions_asked += 1
        return replace(request, id=f"d{self._decisions_asked}")

    async def _ask[D: Decision](
        self, request: DecisionRequest, answer: type[D], heard: Sequence[Event] = ()
    ) -> Decided[D]:
        view = perceived_by([*self.log.events, *heard], request.resident)
        with (
            bound_contextvars(resident=request.resident, decision=request.id),
            tracing.new_trace(
                f"decision.{request.kind}",
                self._trace_labels(request),
                tags=[self.state.phase, request.kind],
            ),
        ):
            reply = await self.brains[request.resident].decide(request, view)
        decision = reply.decision
        if not isinstance(decision, answer):
            raise IllegalDecisionError(f"{request} was answered with {decision!r}")
        if problem := why_illegal(request, decision):
            raise IllegalDecisionError(f"{request.resident}'s {request.kind}: {problem}")
        return Decided(request=request, decision=decision, fallback_reason=reply.fallback_reason)


async def play_game(
    config: GameConfig,
    brain_for: BrainFactory,
    observers: Sequence[EventObserver] = (),
    clock: Callable[[], float] = time.monotonic,
    game_id: str = "",
) -> GameResult:
    """Play one whole game. Observers hear every event as it is appended.

    `game_id` names the game in logs and traces; a fresh one is made if none is given.
    """
    game = Game(config, brain_for, observers, clock, game_id)
    await game.play()
    return GameResult(events=game.log.events, state=game.state)
