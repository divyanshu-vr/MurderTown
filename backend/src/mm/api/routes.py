"""HTTP and WebSocket routes.

Only the Host, who sends the Host token, may start games or see a game's full scope.
Everyone else is a Spectator with public scope: sent only what the whole town saw.
Sequence numbers and decision ids keep their gaps in public scope. They count the events
the town did not see, which tells it no more than its deaths and its rules already do.
"""

import asyncio
import secrets
from collections.abc import AsyncGenerator
from contextlib import aclosing
from dataclasses import asdict, dataclass
from datetime import datetime
from math import ceil
from typing import Annotated, Literal

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Path,
    Query,
    Request,
    WebSocket,
    WebSocketDisconnect,
)
from pydantic import BaseModel

from mm.agents import CallSummary, Cost, ModelCall
from mm.agents.memory import Mind, mind_of
from mm.api.live_games import Control, ControlRefusedError, LiveGames
from mm.api.rate_limit import RateLimit
from mm.engine import GameConfig, Phase, Side
from mm.engine.config import SCRIPTED_PROVIDER
from mm.engine.decisions import DECISION_ID, decision_number
from mm.engine.events import Event, ends_the_game
from mm.llm.prices import priced_models
from mm.llm.providers import NAMES
from mm.orchestrator.narrator import NARRATOR
from mm.persistence import Bus, GameStatus, GameStore, StoredGame
from mm.review import Review, review_of

router = APIRouter()


HOST_TOKEN_HEADER = "X-Host-Token"

TOKEN_WAIT_S = 10.0
"""How long a full-scope socket has to send the Host token before it is closed."""

NOT_THE_HOST = 4401
"""How a socket that did not send the Host token is closed."""

MAX_SEED = 2**53
"""Random seeds stay below it, so a browser reads them exactly."""


@dataclass(frozen=True)
class Services:
    store: GameStore
    bus: Bus
    games: LiveGames
    host_token: str
    new_games: RateLimit

    def is_host(self, token: str) -> bool:
        return secrets.compare_digest(token.encode(), self.host_token.encode())


def get_services(request: Request) -> Services:
    found: Services = request.app.state.services
    return found


ServicesDep = Annotated[Services, Depends(get_services)]


class GameCreated(BaseModel):
    id: str


class GameSummary(BaseModel):
    """A game at a glance. Its configuration is left out, since its seed would tell every role;
    full scope reads it from the game's first event."""

    id: str
    status: GameStatus
    winner: Side | None
    created_at: datetime
    last_seq: int
    day: int
    phase: Phase
    cost_usd: float | None
    """Its Equivalent cost so far, for the Host only: how it grows could tell who acts at Night."""
    controls: list[Control]
    """What the Host may do to it now; nothing, for anyone else."""


class GameList(BaseModel):
    games: list[GameSummary]


class SetupChoices(BaseModel):
    """What the setup form may offer: every provider, and every model with a price. A provider
    with no API key here is refused when a game is started, saying which key it needs."""

    providers: list[str]
    models: list[str]


class EventPage(BaseModel):
    events: list[Event]


class CallPage(BaseModel):
    calls: list[CallSummary]


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


def scope_of(request: Request, services: ServicesDep) -> Scope:
    """A request carrying the Host token has full scope, and one carrying none public scope.
    A wrong token is refused rather than given less, so a mistyped one is noticed."""
    token = request.headers.get(HOST_TOKEN_HEADER)
    if token is None:
        return "public"
    if not services.is_host(token):
        raise HTTPException(status_code=401, detail="That is not the Host token")
    return "full"


ScopeDep = Annotated[Scope, Depends(scope_of)]


def host_only(scope: ScopeDep) -> None:
    """Refuse anyone but the Host: only they may start or control games, or look inside one."""
    if scope != "full":
        detail = f"Only the Host may do this: send the Host token in {HOST_TOKEN_HEADER}"
        raise HTTPException(status_code=401, detail=detail)


HostOnly = Depends(host_only)


@router.get("/healthz")
async def healthz() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/readyz")
async def readyz(services: ServicesDep) -> dict[str, str]:
    await services.store.ping()
    return {"status": "ready"}


@router.post("/games", status_code=201, dependencies=[HostOnly])
async def create_game(config: GameConfig, services: ServicesDep) -> GameCreated:
    """Start a game; one whose lineup cannot be played is refused, and nothing is stored.
    A game given no seed is dealt a random one: a known seed would tell every role."""
    if wait := services.new_games.take():  # taken before any await, so a burst cannot slip by
        retry = str(ceil(wait))
        detail = f"Too many new games this hour: try again in {retry} seconds"
        raise HTTPException(status_code=429, detail=detail, headers={"Retry-After": retry})
    if "seed" not in config.model_fields_set:
        config = config.model_copy(update={"seed": secrets.randbelow(MAX_SEED)})
    try:
        return GameCreated(id=await services.games.start(config))
    except ValueError as cannot_play:
        services.new_games.give_back()
        raise HTTPException(status_code=422, detail=str(cannot_play)) from cannot_play


@router.get("/setup-choices")
async def setup_choices() -> SetupChoices:
    return SetupChoices(providers=[SCRIPTED_PROVIDER, *NAMES], models=priced_models())


@router.get("/games")
async def list_games(
    services: ServicesDep, scope: ScopeDep, limit: Annotated[int, Query(ge=1, le=200)] = 50
) -> GameList:
    """The latest games, newest first."""
    games = await services.store.games(limit)
    return GameList(games=[at_a_glance(services, game, scope) for game in games])


@router.get("/games/{game_id}")
async def get_game(game_id: str, services: ServicesDep, scope: ScopeDep) -> GameSummary:
    return await summary_of(services, game_id, scope)


@router.post("/games/{game_id}/{control}", dependencies=[HostOnly])
async def control_game(game_id: str, control: Control, services: ServicesDep) -> GameSummary:
    """Pause a game before its next batch of decisions, step a paused game one batch, or
    resume it. Only a game being played can be controlled."""
    await summary_of(services, game_id, "full")
    try:
        await services.games.control(game_id, control)
    except ControlRefusedError as refused:
        raise HTTPException(status_code=409, detail=str(refused)) from refused
    return await summary_of(services, game_id, "full")


async def summary_of(services: Services, game_id: str, scope: Scope) -> GameSummary:
    return at_a_glance(services, await stored_game(services, game_id), scope)


async def stored_game(services: Services, game_id: str) -> StoredGame:
    """The game, or a 404 if there is none."""
    game = await services.store.game(game_id)
    if game is None:
        raise HTTPException(status_code=404, detail="No such game")
    return game


def at_a_glance(services: Services, game: StoredGame, scope: Scope) -> GameSummary:
    """A stored game as `scope` may see it: its cost and controls are the Host's alone."""
    host = scope == "full"
    return GameSummary.model_validate(
        {
            **asdict(game),
            "cost_usd": game.cost_usd if host else None,
            "controls": services.games.offered(game.id) if host else [],
        }
    )


@router.get("/games/{game_id}/events")
async def get_events(
    game_id: str,
    services: ServicesDep,
    scope: ScopeDep,
    after: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int | None, Query(ge=1, le=5000)] = None,
) -> EventPage:
    public = scope == "public"
    return EventPage(
        events=await services.store.events(game_id, after=after, limit=limit, public=public)
    )


@router.get("/games/{game_id}/residents/{name}/mind", dependencies=[HostOnly])
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


@router.get("/games/{game_id}/events/{seq}/explain", dependencies=[HostOnly])
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


@router.get("/games/{game_id}/model-calls", dependencies=[HostOnly])
async def list_model_calls(
    game_id: str,
    services: ServicesDep,
    resident: str | None = None,
    after: Annotated[str | None, Query(pattern=DECISION_ID)] = None,
    limit: Annotated[int, Query(ge=1, le=1000)] = 100,
) -> CallPage:
    """A page of a game's model calls (or one Resident's), without their words: every attempt
    at the `limit` decisions asked after decision `after`. The next page is after the last
    call's decision (`GameStore.call_page`)."""
    await stored_game(services, game_id)
    calls = await services.store.call_page(
        game_id, resident=resident, after=decision_number(after) if after else 0, decisions=limit
    )
    return CallPage(calls=calls)


@router.get("/games/{game_id}/model-calls/{decision_id}/{attempt}", dependencies=[HostOnly])
async def get_model_call(
    game_id: str,
    decision_id: Annotated[str, Path(pattern=DECISION_ID)],
    attempt: Annotated[int, Path(ge=1)],
    services: ServicesDep,
) -> ModelCall:
    """One model call, whole: the prompt it was given, what came back, and any problem with it."""
    await stored_game(services, game_id)
    call = await services.store.call(game_id, decision_id, attempt)
    if call is None:
        raise HTTPException(status_code=404, detail=f"No attempt {attempt} at {decision_id}")
    return call


@router.get("/games/{game_id}/cost", dependencies=[HostOnly])
async def cost(game_id: str, services: ServicesDep) -> CostReport:
    """Full scope only: what each Resident's calls cost reveals who acts at Night."""
    await stored_game(services, game_id)
    residents = await services.store.cost(game_id)
    narrator = residents.pop(NARRATOR.name, Cost())
    return CostReport(
        total=sum(residents.values(), narrator), residents=residents, narrator=narrator
    )


@router.get("/games/{game_id}/review", dependencies=[HostOnly])
async def review(game_id: str, services: ServicesDep) -> Review:
    """The review of the events stored so far. Host only: it shows private beliefs and roles."""
    await stored_game(services, game_id)
    return review_of(await services.store.events(game_id))


@router.websocket("/ws/games/{game_id}")
async def stream_game(
    socket: WebSocket, game_id: str, after: int = 0, scope: Scope = "public"
) -> None:
    """Send every event after `after` that `scope` may see, stored or still to come, and close
    when the game ends or is aborted. A browser cannot put a header on a socket, so a
    full-scope socket sends the Host token as its first message."""
    services: Services = socket.app.state.services
    await socket.accept()
    if await services.store.game(game_id) is None:
        await socket.close(code=4404, reason="No such game")
        return
    if scope == "full":
        try:
            token = await asyncio.wait_for(socket.receive_text(), TOKEN_WAIT_S)
        except WebSocketDisconnect:
            return
        except TimeoutError:
            token = ""
        if not services.is_host(token):
            await socket.close(code=NOT_THE_HOST, reason="That is not the Host token")
            return

    public = scope == "public"
    async with aclosing(backlog_then_live(services, game_id, after, public)) as events:
        async for event in events:
            await socket.send_text(event.model_dump_json())
            if ends_the_game(event.payload):
                break
    await socket.close()


async def backlog_then_live(
    services: Services, game_id: str, after: int, public: bool
) -> AsyncGenerator[Event]:
    """A game's stored events after `after`, then its new events as they happen; with `public`,
    only those the whole town perceived.

    Subscribing before reading the backlog means no event can slip between the
    two; an event that arrives both ways is yielded once, by its sequence number.
    """
    with services.bus.subscribe(game_id) as live:
        last = after
        for event in await services.store.events(game_id, after=after, public=public):
            last = event.seq
            yield event
        while True:
            event = await live.get()
            if event.seq > last and (event.visibility.public or not public):
                last = event.seq
                yield event
