"""HTTP and WebSocket routes."""

from collections.abc import AsyncGenerator
from contextlib import aclosing
from dataclasses import dataclass
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request, WebSocket
from pydantic import BaseModel

from mm.agents import Cost, ModelCall
from mm.agents.memory import Mind, mind_of
from mm.api.live_games import LiveGames
from mm.engine import GameConfig, Side
from mm.engine.events import Event, ends_the_game
from mm.orchestrator.narrator import NARRATOR
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


class Explanation(BaseModel):
    """The decision behind an event: every model attempt at it, and the fallback if one was used.

    A decision made by a scripted bot has no attempts, because no model was asked.
    """

    event: Event
    attempts: list[ModelCall]
    fallback_reason: str | None


class CostReport(BaseModel):
    """What a game's model calls cost: in all, for each Resident, and for the narrator,
    who is not a Resident. The Residents' rows and the narrator's add up to the total."""

    total: Cost
    residents: dict[str, Cost]
    narrator: Cost


Scope = Literal["public", "full"]
"""How much of a game a request may see: only what the whole town saw, or everything."""


def full_scope(scope: Scope = "full") -> None:
    """Refuse a request for something only full scope may see.

    The one place that decides who may have full scope; an admin token will be
    required here once the Host has one.
    """
    if scope != "full":
        raise HTTPException(status_code=403, detail="Only full scope may see this")


FullScope = Depends(full_scope)


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


@router.get("/games/{game_id}/residents/{name}/mind", dependencies=[FullScope])
async def get_mind(
    game_id: str, name: str, services: ServicesDep, at: Annotated[int | None, Query(ge=1)] = None
) -> Mind:
    """One Resident's mind as of sequence number `at` (or now), built as their prompts are.

    Sequence numbers run from 1 without gaps, so the first `at` events are the ones up to `at`.
    """
    mind = mind_of(await services.store.events(game_id, limit=at), name)
    if mind is None:
        raise HTTPException(status_code=404, detail=f"No Resident called {name} at that moment")
    return mind


@router.get("/games/{game_id}/events/{seq}/explain", dependencies=[FullScope])
async def explain(game_id: str, seq: int, services: ServicesDep) -> Explanation:
    store = services.store
    event = await store.event(game_id, seq)
    if event is None or event.decision_id is None:
        raise HTTPException(status_code=404, detail=f"Event {seq} was not caused by a decision")
    return Explanation(
        event=event,
        attempts=await store.calls(game_id, event.decision_id),
        fallback_reason=await store.fallback_reason(game_id, event.decision_id),
    )


@router.get("/games/{game_id}/cost", dependencies=[FullScope])
async def cost(game_id: str, services: ServicesDep) -> CostReport:
    """Full scope only: what each Resident's calls cost reveals who acts at Night."""
    if await services.store.game(game_id) is None:
        raise HTTPException(status_code=404, detail="No such game")
    residents = await services.store.cost(game_id)
    narrator = residents.pop(NARRATOR.name, Cost())
    return CostReport(
        total=sum(residents.values(), narrator), residents=residents, narrator=narrator
    )


@router.websocket("/ws/games/{game_id}")
async def stream_game(socket: WebSocket, game_id: str, after: int = 0) -> None:
    """Send every event after `after`, stored or still to come, and close when the game ends
    or is aborted."""
    services: Services = socket.app.state.services
    await socket.accept()
    if await services.store.game(game_id) is None:
        await socket.close(code=4404, reason="No such game")
        return

    async with aclosing(backlog_then_live(services, game_id, after)) as events:
        async for event in events:
            await socket.send_text(event.model_dump_json())
            if ends_the_game(event.payload):
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
