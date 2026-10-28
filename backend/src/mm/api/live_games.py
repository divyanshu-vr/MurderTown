"""Live games: each game runs as a background task inside the API process.

Every event is stored first and published second, so a Spectator who reads the
stored backlog and then follows the live bus can never miss one. Every model
call is stored too, before the event its decision causes.
"""

import asyncio
import logging
from collections.abc import Callable

from mm.agents import BrainFactory, CallRecorder, ModelCall, scripted_bots
from mm.engine import GameConfig
from mm.engine.events import Event
from mm.orchestrator import play_game
from mm.persistence import Bus, GameStore

logger = logging.getLogger(__name__)

BrainsFor = Callable[[GameConfig, CallRecorder], BrainFactory]
"""Chooses the decision source for every Resident of a new game; Agents record their calls."""


def scripted_brains(config: GameConfig, record: CallRecorder) -> BrainFactory:
    return scripted_bots(config.seed)  # scripted bots call no model, so there is nothing to record


class LiveGames:
    def __init__(self, store: GameStore, bus: Bus, brains_for: BrainsFor) -> None:
        self.store, self.bus, self.brains_for = store, bus, brains_for
        self._tasks: set[asyncio.Task[None]] = set()

    async def start(self, config: GameConfig) -> str:
        game_id = await self.store.create_game(config)
        task = asyncio.create_task(self._play(game_id, config), name=f"game-{game_id}")
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)
        return game_id

    async def _play(self, game_id: str, config: GameConfig) -> None:
        async def store(event: Event) -> None:
            await self.store.append_event(game_id, event)

        async def publish(event: Event) -> None:
            await self.bus.publish(game_id, event)

        async def record(call: ModelCall) -> None:
            await self.store.record_call(game_id, call)

        try:
            brains = self.brains_for(config, record)
            result = await play_game(config, brains, observers=[store, publish], game_id=game_id)
        except Exception:
            logger.exception("game %s failed", game_id)
            await self.store.set_status(game_id, "failed")
            return
        await self.store.set_status(game_id, "finished", winner=result.state.winner)

    async def shutdown(self) -> None:
        for task in self._tasks:
            task.cancel()
        await asyncio.gather(*self._tasks, return_exceptions=True)
