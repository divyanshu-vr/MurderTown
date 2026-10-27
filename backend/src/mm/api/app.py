"""The FastAPI application: wires the store, the live bus and live games together."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import create_async_engine

from mm.api.live_games import BrainsFor, LiveGames, scripted_brains
from mm.api.routes import Services, router
from mm.api.settings import Settings
from mm.persistence import GameStore, InProcessBus, upgrade


def create_app(
    settings: Settings | None = None, brains_for: BrainsFor = scripted_brains
) -> FastAPI:
    settings = settings or Settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        _ensure_sqlite_folder(settings.database_url)
        engine = create_async_engine(settings.database_url)
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


def _ensure_sqlite_folder(database_url: str) -> None:
    url = make_url(database_url)
    if url.get_backend_name() == "sqlite" and url.database:
        Path(url.database).parent.mkdir(parents=True, exist_ok=True)
