"""The game store: where games and their event logs are kept."""

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Literal
from uuid import uuid4

from sqlalchemy import func, select, text, update
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker

from mm.engine import GameConfig, Side
from mm.engine.events import Event
from mm.persistence.tables import EventRow, GameRow

GameStatus = Literal["running", "finished", "failed"]


@dataclass(frozen=True)
class StoredGame:
    id: str
    config: GameConfig
    status: GameStatus
    winner: Side | None
    last_seq: int


class GameStore:
    def __init__(self, engine: AsyncEngine) -> None:
        self._engine = engine
        self._sessions = async_sessionmaker(engine, expire_on_commit=False)

    async def ping(self) -> None:
        async with self._engine.connect() as connection:
            await connection.execute(text("SELECT 1"))

    async def create_game(self, config: GameConfig) -> str:
        game_id = uuid4().hex
        async with self._sessions.begin() as session:
            session.add(
                GameRow(
                    id=game_id,
                    config=config.model_dump(mode="json"),
                    status="running",
                    winner=None,
                    created_at=datetime.now(UTC),
                )
            )
        return game_id

    async def append_event(self, game_id: str, event: Event) -> None:
        async with self._sessions.begin() as session:
            session.add(
                EventRow(
                    game_id=game_id,
                    seq=event.seq,
                    day=event.day,
                    phase=event.phase,
                    type=event.payload.type,
                    visibility=event.visibility.model_dump(mode="json"),
                    payload=event.payload.model_dump(mode="json"),
                )
            )

    async def set_status(
        self, game_id: str, status: GameStatus, winner: Side | None = None
    ) -> None:
        async with self._sessions.begin() as session:
            await session.execute(
                update(GameRow).where(GameRow.id == game_id).values(status=status, winner=winner)
            )

    async def game(self, game_id: str) -> StoredGame | None:
        async with self._sessions() as session:
            row = await session.get(GameRow, game_id)
            if row is None:
                return None
            last_seq = await session.scalar(
                select(func.coalesce(func.max(EventRow.seq), 0)).where(EventRow.game_id == game_id)
            )
        return StoredGame(
            id=row.id,
            config=GameConfig.model_validate(row.config),
            status=row.status,  # type: ignore[arg-type]
            winner=Side(row.winner) if row.winner else None,
            last_seq=last_seq or 0,
        )

    async def events(self, game_id: str, after: int = 0, limit: int | None = None) -> list[Event]:
        """A game's events with a sequence number above `after`, oldest first."""
        query = (
            select(EventRow)
            .where(EventRow.game_id == game_id, EventRow.seq > after)
            .order_by(EventRow.seq)
            .limit(limit)
        )
        async with self._sessions() as session:
            rows = (await session.scalars(query)).all()
        return [
            Event.model_validate(
                {
                    "seq": row.seq,
                    "day": row.day,
                    "phase": row.phase,
                    "visibility": row.visibility,
                    "payload": row.payload,
                }
            )
            for row in rows
        ]
