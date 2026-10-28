"""The FastAPI application: wires the store, the live bus and live games together."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager, nullcontext

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from mm.api.live_games import BrainsFor, LiveGames, scripted_brains
from mm.api.routes import Services, router
from mm.api.settings import Settings
from mm.observability import observed
from mm.persistence import GameStore, InProcessBus, open_database, upgrade


def create_app(
    settings: Settings | None = None,
    brains_for: BrainsFor = scripted_brains,
    observe: bool = False,
) -> FastAPI:
    """The API. With `observe`, the server process sends logs and traces where the
    environment says; tests leave it off, so they never send spans anywhere."""
    settings = settings or Settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        with observed() if observe else nullcontext():
            async with serving(app):
                yield

    @asynccontextmanager
    async def serving(app: FastAPI) -> AsyncIterator[None]:
        engine = open_database(settings.database_url)
        await upgrade(engine)
        store, bus = GameStore(engine), InProcessBus()
        games = LiveGames(store, bus, brains_for)
        app.state.services = Services(store=store, bus=bus, games=games)
        yield
        await games.shutdown()
        await engine.dispose()

    app = FastAPI(title="MurderTown", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(router)
    return app


def observed_app() -> FastAPI:
    """The app `mm serve` runs: in every server process, reloads included, logs and traces
    are set up from the environment."""
    return create_app(observe=True)
