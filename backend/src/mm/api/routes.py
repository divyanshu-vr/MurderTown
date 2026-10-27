"""HTTP and WebSocket routes."""

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


def services(request: Request) -> Services:
    found: Services = request.app.state.services
    return found


ServicesDep = Annotated[Services, Depends(services)]


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
async def readyz(app: ServicesDep) -> dict[str, str]:
    await app.store.ping()
    return {"status": "ready"}


@router.post("/games", status_code=201)
async def create_game(config: GameConfig, app: ServicesDep) -> GameCreated:
    return GameCreated(id=await app.games.start(config))


@router.get("/games/{game_id}")
async def get_game(game_id: str, app: ServicesDep) -> GameSummary:
    game = await app.store.game(game_id)
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
    app: ServicesDep,
    after: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int | None, Query(ge=1, le=5000)] = None,
) -> EventPage:
    return EventPage(events=await app.store.events(game_id, after=after, limit=limit))


@router.websocket("/ws/games/{game_id}")
async def stream_game(socket: WebSocket, game_id: str, after: int = 0) -> None:
    """Send the stored backlog after `after`, then every new event, ending with the game.

    Subscribing before reading the backlog means no event can slip between the
    two; anything seen twice is dropped by its sequence number.
    """
    app: Services = socket.app.state.services
    await socket.accept()
    if await app.store.game(game_id) is None:
        await socket.close(code=4404, reason="No such game")
        return

    with app.bus.subscribe(game_id) as live:
        last_sent = after
        for event in await app.store.events(game_id, after=after):
            await socket.send_text(event.model_dump_json())
            last_sent = event.seq
            if isinstance(event.payload, GameEnded):
                await socket.close()
                return
        while True:
            event = await live.get()
            if event.seq <= last_sent:
                continue
            await socket.send_text(event.model_dump_json())
            last_sent = event.seq
            if isinstance(event.payload, GameEnded):
                await socket.close()
                return
