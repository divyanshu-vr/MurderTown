"""The FastAPI application: wires the store, the live bus and live games together."""

from collections.abc import AsyncIterator, Mapping
from contextlib import asynccontextmanager, nullcontext

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from mm.api.live_games import BrainsFor, LiveGames, lineup_on
from mm.api.routes import Services, router
from mm.api.settings import Settings
from mm.llm import ModelProvider
from mm.observability import observed
from mm.persistence import GameStore, InProcessBus, open_database, upgrade


def create_app(
    settings: Settings | None = None,
    brains_for: BrainsFor | None = None,
    providers: Mapping[str, ModelProvider] | None = None,
    observe: bool = False,
) -> FastAPI:
    """The API. Each game is played as its lineup says, on `providers` (by default, those
    the settings reach); tests may pass their own decision sources as `brains_for`. With
    `observe`, the server process sends logs and traces where the environment says; tests
    leave it off, so they never send spans anywhere."""
    settings = settings or Settings()
    brains_for = brains_for or lineup_on(
        providers if providers is not None else settings.providers()
    )

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
        await games.unfinished_at_start(resume=settings.resume_on_boot)
        yield
        await games.shutdown(settings.shutdown_grace_seconds)
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
