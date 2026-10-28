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
from collections.abc import Callable, Sequence

import structlog

from mm.agents import BrainFactory, CallRecorder, ModelCall, scripted_bots
from mm.engine import GameConfig
from mm.engine.events import Event
from mm.orchestrator import GameHaltedError, play_game
from mm.persistence import Bus, GameStatus, GameStore

logger = structlog.get_logger(__name__)

BrainsFor = Callable[[GameConfig, CallRecorder, Sequence[ModelCall]], BrainFactory]
"""Chooses the decision source for every Resident of a game. Agents record their calls, and
a resumed game's Agents answer again from the calls it had recorded (empty for a new game)."""


def scripted_brains(
    config: GameConfig, record: CallRecorder, replay: Sequence[ModelCall]
) -> BrainFactory:
    return scripted_bots(config.seed)  # scripted bots call no model, so there is nothing to record


class LiveGames:
    def __init__(self, store: GameStore, bus: Bus, brains_for: BrainsFor) -> None:
        self.store, self.bus, self.brains_for = store, bus, brains_for
        self._tasks: set[asyncio.Task[None]] = set()
        self._halt = asyncio.Event()
        """Set on shutdown: every game stops before its next decision."""

    async def start(self, config: GameConfig) -> str:
        game_id = await self.store.create_game(config)
        self._run(game_id, config)
        return game_id

    async def resume_unfinished(self) -> None:
        """Start again every game the server left running, from what it had stored."""
        for game in await self.store.unfinished():
            events = await self.store.events(game.id)
            calls = await self.store.calls(game.id)
            logger.info("game resumed", game=game.id, events=len(events), calls=len(calls))
            self._run(game.id, game.config, events, calls)

    def _run(
        self,
        game_id: str,
        config: GameConfig,
        replay: Sequence[Event] = (),
        calls: Sequence[ModelCall] = (),
    ) -> None:
        task = asyncio.create_task(
            self._play(game_id, config, replay, calls), name=f"game-{game_id}"
        )
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)

    async def _play(
        self,
        game_id: str,
        config: GameConfig,
        replay: Sequence[Event],
        calls: Sequence[ModelCall],
    ) -> None:
        async def store(event: Event) -> None:
            await self.store.append_event(game_id, event)

        async def publish(event: Event) -> None:
            await self.bus.publish(game_id, event)

        async def record(call: ModelCall) -> None:
            await self.store.record_call(game_id, call)

        try:
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
