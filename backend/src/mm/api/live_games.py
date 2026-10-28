"""Live games: each game runs as a background task inside the API process.

Every event is stored first and published second, so a Spectator who reads the
stored backlog and then follows the live bus can never miss one. Every model
call is stored too, before the event its decision causes.

A game the server left running (it crashed, or was stopped) resumes at the next
start: it replays from its seed over what it had stored, answering recorded model
calls from their records, and then goes on. On shutdown, games stop before their
next decision; decisions already asked finish first, so their calls are recorded.
"""

import asyncio
from collections.abc import Callable, Mapping, Sequence

import structlog

from mm.agents import BrainFactory, CallRecorder, ModelCall
from mm.agents.calls import unrecorded
from mm.agents.lineup import lineup_brains
from mm.engine import GameConfig
from mm.engine.events import Event
from mm.llm import ModelProvider
from mm.orchestrator import GameHaltedError, play_game
from mm.persistence import Bus, GameStatus, GameStore

logger = structlog.get_logger(__name__)

BrainsFor = Callable[[GameConfig, CallRecorder, Sequence[ModelCall]], BrainFactory]
"""Chooses the decision source for every Resident of a game. Agents record their calls, and
a resumed game's Agents answer again from the calls it had recorded (empty for a new game)."""


def lineup_on(providers: Mapping[str, ModelProvider]) -> BrainsFor:
    """Decision sources as each game's lineup says, on these providers."""

    def brains_for(
        config: GameConfig, record: CallRecorder, recorded: Sequence[ModelCall]
    ) -> BrainFactory:
        return lineup_brains(config, providers, record, recorded)

    return brains_for


class LiveGames:
    def __init__(self, store: GameStore, bus: Bus, brains_for: BrainsFor) -> None:
        self.store, self.bus, self.brains_for = store, bus, brains_for
        self._tasks: set[asyncio.Task[None]] = set()
        self._halt = asyncio.Event()
        """Set on shutdown: every game stops before its next decision."""

    async def start(self, config: GameConfig) -> str:
        """Store and start a game. A lineup that cannot be played (a provider not available,
        a model with no price) is refused first, with a `ValueError`. Making a provider may
        check a login, so it happens off the event loop."""
        await asyncio.to_thread(self.brains_for, config, unrecorded, ())
        game_id = await self.store.create_game(config)
        self._run(game_id, config)
        return game_id

    async def unfinished_at_start(self, resume: bool) -> None:
        """Resume every game the server left running, or, when told not to, list them."""
        for game in await self.store.unfinished():
            if resume:
                self._run(game.id, game.config, resuming=True)
            else:
                logger.warning("game left running, not resumed", game=game.id)

    def _run(self, game_id: str, config: GameConfig, resuming: bool = False) -> None:
        task = asyncio.create_task(self._play(game_id, config, resuming), name=f"game-{game_id}")
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)

    async def _play(self, game_id: str, config: GameConfig, resuming: bool) -> None:
        async def store(event: Event) -> None:
            await self.store.append_event(game_id, event)

        async def publish(event: Event) -> None:
            await self.bus.publish(game_id, event)

        async def record(call: ModelCall) -> None:
            await self.store.record_call(game_id, call)

        try:
            replay = await self.store.events(game_id) if resuming else []
            calls = await self.store.calls(game_id) if resuming else []
            if resuming:
                logger.info("game resumed", game=game_id, events=len(replay), calls=len(calls))
            result = await play_game(
                config,
                self.brains_for(config, record, calls),
                observers=[store, publish],
                game_id=game_id,
                replay=replay,
                halt=self._halt,
            )
        except GameHaltedError:
            logger.info("game halted", game=game_id)  # still running: it resumes next time
            return
        except Exception:
            logger.exception("game failed", game=game_id)
            await self.store.set_status(game_id, "failed")
            return
        status: GameStatus = "aborted" if result.state.aborted else "finished"
        await self.store.set_status(game_id, status, winner=result.state.winner)

    async def shutdown(self, grace_s: float) -> None:
        """Stop every game before its next decision, give the decisions already asked up to
        `grace_s` seconds to finish and be recorded, then cancel whatever is left."""
        self._halt.set()
        if not self._tasks:
            return
        _, unfinished = await asyncio.wait(self._tasks, timeout=grace_s)
        for task in unfinished:
            task.cancel()
        await asyncio.gather(*unfinished, return_exceptions=True)
