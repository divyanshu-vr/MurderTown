"""HTTP and WebSocket routes."""

from collections.abc import AsyncGenerator
from contextlib import aclosing
from dataclasses import dataclass
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request, WebSocket
from pydantic import BaseModel

from mm.api.live_games import LiveGames
from mm.engine import GameConfig, Side
from mm.engine.events import Event, GameEnded
from mm.persistence import Bus, GameStatus, GameStore

router = APIRouter()


@dataclass(frozen=True)
class Services:
    store: GameStore
    bus: Bus
    games: LiveGames


def get_services(request: Request) -> Services:
    found: Services = request.app.state.services
    return found


ServicesDep = Annotated[Services, Depends(get_services)]


class GameCreated(BaseModel):
    id: str


class GameSummary(BaseModel):
    id: str
    status: GameStatus
    config: GameConfig
    winner: Side | None
    last_seq: int


class EventPage(BaseModel):
    events: list[Event]


@router.get("/healthz")
async def healthz() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/readyz")
async def readyz(services: ServicesDep) -> dict[str, str]:
    await services.store.ping()
    return {"status": "ready"}


@router.post("/games", status_code=201)
async def create_game(config: GameConfig, services: ServicesDep) -> GameCreated:
    return GameCreated(id=await services.games.start(config))


@router.get("/games/{game_id}")
async def get_game(game_id: str, services: ServicesDep) -> GameSummary:
    game = await services.store.game(game_id)
    if game is None:
        raise HTTPException(status_code=404, detail="No such game")
    return GameSummary(
        id=game.id,
        status=game.status,
        config=game.config,
        winner=game.winner,
        last_seq=game.last_seq,
    )


@router.get("/games/{game_id}/events")
async def get_events(
    game_id: str,
    services: ServicesDep,
    after: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int | None, Query(ge=1, le=5000)] = None,
) -> EventPage:
    return EventPage(events=await services.store.events(game_id, after=after, limit=limit))


@router.websocket("/ws/games/{game_id}")
async def stream_game(socket: WebSocket, game_id: str, after: int = 0) -> None:
    """Send every event after `after`, stored or still to come, and close when the game ends."""
    services: Services = socket.app.state.services
    await socket.accept()
    if await services.store.game(game_id) is None:
        await socket.close(code=4404, reason="No such game")
        return

    async with aclosing(backlog_then_live(services, game_id, after)) as events:
        async for event in events:
            await socket.send_text(event.model_dump_json())
            if isinstance(event.payload, GameEnded):
                break
    await socket.close()


async def backlog_then_live(services: Services, game_id: str, after: int) -> AsyncGenerator[Event]:
    """A game's stored events after `after`, then its new events as they happen.

    Subscribing before reading the backlog means no event can slip between the
    two; an event that arrives both ways is yielded once, by its sequence number.
    """
    with services.bus.subscribe(game_id) as live:
        last = after
        for event in await services.store.events(game_id, after=after):
            last = event.seq
            yield event
        while True:
            event = await live.get()
            if event.seq > last:
                last = event.seq
                yield event
