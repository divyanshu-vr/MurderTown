"""The game runner: plays a whole game from casting to the final verdict."""

import asyncio
from collections.abc import Awaitable, Callable, Sequence
from contextlib import nullcontext
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
    DecisionUnanswered,
    Event,
    EventPayload,
    GameAborted,
    GameEnded,
    OpenFloorTimedOut,
    PhaseStarted,
)
from mm.engine.perception import perceived_by
from mm.engine.rules import Verdict, roles_revealed, verdict, verdict_at_end_of_day, why_illegal
from mm.engine.state import GameState
from mm.observability import tracing
from mm.orchestrator.controls import GameControls, GameHaltedError
from mm.orchestrator.log import EventLog, EventObserver, ReplayDivergedError
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


INTERNAL_ERROR = "the game stopped on an internal error"
"""What Spectators are told when the game crashes; the details stay in the server's logs."""

DIVERGED = "resuming the game did not reproduce its log"
"""What Spectators are told when a resumed game makes an event different from the stored one."""


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
    """One game being played. `play_game` makes one and plays it to the end."""

    def __init__(
        self,
        config: GameConfig,
        brain_for: BrainFactory,
        log: EventLog,
        *,
        controls: GameControls,
        game_id: str,
    ) -> None:
        self.config = config
        self.controls = controls
        self.clock = controls.now
        self.game_id = game_id
        self.rng = Random(config.seed)
        self.log = log
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
            except GameHaltedError:
                raise  # the game stopped where it can resume: nothing more to log
            except ModelFailureError as failed:
                await self.abort(failed.problem, unanswered=failed.request)
            except Exception as error:
                diverged = isinstance(error, ReplayDivergedError)
                await self.abort(DIVERGED if diverged else INTERNAL_ERROR)
                raise

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
        await self.append(roles_revealed(self.state))
        await self.append(GameEnded(winner=outcome.winner, reason=outcome.reason))
        logger.info("game ended", winner=outcome.winner, reason=outcome.reason)

    async def abort(self, reason: str, unanswered: DecisionRequest | None = None) -> None:
        """End the log with an abort, so everyone sees the game stop and why. A decision that
        got no answer comes first, in full scope only (whose it was could reveal a Night
        role), linked to the decision so the Mind inspector can explain it.

        A resumed game replaying up to an abort it had stored makes that same abort again.
        If its stored log went on instead, the log goes back to it and the abort follows.
        """
        ending: list[tuple[EventPayload, str | None]] = [(GameAborted(reason=reason), None)]
        if unanswered:
            told = DecisionUnanswered(
                resident=unanswered.resident, kind=unanswered.kind, reason=reason
            )
            ending.insert(0, (told, unanswered.id))
        try:
            await self._append_all(ending)
        except ReplayDivergedError:
            await self._append_all(ending)
        resident = unanswered.resident if unanswered else None
        logger.warning("game aborted", resident=resident, reason=reason)

    async def _append_all(self, payloads: Sequence[tuple[EventPayload, str | None]]) -> None:
        for payload, decision_id in payloads:
            await self.log.append(payload, decision_id=decision_id)

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
        await self.controls.checkpoint(replaying=self.log.replaying)
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
        perceives only the part of it their visibility allows. Asking nobody is no batch,
        so it is no checkpoint either.
        """
        if not requests:
            return []
        await self.controls.checkpoint(replaying=self.log.replaying)
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

    def open_floor_out_of_time(self, started: float) -> bool:
        """Whether the Open floor's time limit has passed since `started`. A replay follows
        what the game recorded instead, since its clock reads differently."""
        limit = self.config.open_floor_seconds
        if limit is None:
            return False
        if upcoming := self.log.upcoming():
            return isinstance(upcoming.payload, OpenFloorTimedOut)
        return self.clock() - started >= limit

    async def _ask[D: Decision](
        self, request: DecisionRequest, answer: type[D], heard: Sequence[Event] = ()
    ) -> Decided[D]:
        view = perceived_by([*self.log.events, *heard], request.resident)
        traced = (  # a replayed decision was traced the first time
            nullcontext()
            if self.log.replaying
            else tracing.new_trace(
                f"decision.{request.kind}",
                self._trace_labels(request),
                tags=[self.state.phase, request.kind],
            )
        )
        with bound_contextvars(resident=request.resident, decision=request.id), traced:
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
    *,
    observers: Sequence[EventObserver] = (),
    game_id: str = "",
    replay: Sequence[Event] = (),
    controls: GameControls | None = None,
) -> GameResult:
    """Play one whole game. Observers hear every event as it is appended.

    `game_id` names the game in logs and traces; a fresh one is made if none is given.
    To resume a game that stopped, pass the events it had stored as `replay`: the game
    plays again from the start, checks it makes those same events, and goes on from there.
    `controls` pause, step or halt the game before its next batch of decisions, and keep
    its clock; halting raises `GameHaltedError` once the decisions already asked finish,
    so the game can be resumed later.
    """
    log = EventLog(observers, replay)
    game_id = game_id or uuid4().hex
    game = Game(config, brain_for, log, controls=controls or GameControls(), game_id=game_id)
    await game.play()
    return GameResult(events=game.log.events, state=game.state)
