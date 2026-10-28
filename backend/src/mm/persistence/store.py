"""The game store: where games, their event logs and their model calls are kept."""

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Literal, cast
from uuid import uuid4

from sqlalchemy import Select, func, select, text, update
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker

from mm.agents import Cost, ModelCall
from mm.engine import GameConfig, Side
from mm.engine.events import Event
from mm.persistence.tables import EventRow, GameRow, ModelCallRow

GameStatus = Literal["running", "finished", "aborted", "failed"]
"""A game is aborted when the model gave no answer; it failed when the game itself crashed."""


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
                    decision_id=event.decision_id,
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
            status=cast(GameStatus, row.status),
            winner=Side(row.winner) if row.winner else None,
            last_seq=last_seq or 0,
        )

    async def unfinished(self) -> list[StoredGame]:
        """Games still running: the server stopped before they ended."""
        async with self._sessions() as session:
            ids = (
                await session.scalars(select(GameRow.id).where(GameRow.status == "running"))
            ).all()
        return [game for game_id in ids if (game := await self.game(game_id))]

    async def events(self, game_id: str, after: int = 0, limit: int | None = None) -> list[Event]:
        """A game's events with a sequence number above `after`, oldest first."""
        query = select(EventRow).where(EventRow.game_id == game_id, EventRow.seq > after)
        return await self._events(query.order_by(EventRow.seq).limit(limit))

    async def event(self, game_id: str, seq: int) -> Event | None:
        query = select(EventRow).where(EventRow.game_id == game_id, EventRow.seq == seq)
        found = await self._events(query)
        return found[0] if found else None

    async def fallback_reason(self, game_id: str, decision_id: str) -> str | None:
        """Why a decision fell back to a safe default, or None if it did not."""
        query = select(EventRow.payload).where(
            EventRow.game_id == game_id,
            EventRow.decision_id == decision_id,
            EventRow.type == "decision_fell_back",
        )
        async with self._sessions() as session:
            fell_back = await session.scalar(query)
        return str(fell_back["reason"]) if fell_back else None

    async def record_call(self, game_id: str, call: ModelCall) -> None:
        async with self._sessions.begin() as session:
            session.add(ModelCallRow(game_id=game_id, **call.model_dump(mode="json")))

    async def calls(self, game_id: str, decision_id: str | None = None) -> list[ModelCall]:
        """Every model attempt at one decision, in order; or, with no decision, every attempt
        the game has made."""
        query = select(ModelCallRow).where(ModelCallRow.game_id == game_id)
        if decision_id is not None:
            query = query.where(ModelCallRow.decision_id == decision_id)
        async with self._sessions() as session:
            rows = (await session.scalars(query.order_by(ModelCallRow.attempt))).all()
        return [ModelCall.model_validate(row, from_attributes=True) for row in rows]

    async def cost(self, game_id: str) -> dict[str, Cost]:
        """What each caller's model calls cost in one game: each Resident's, and the narrator's."""
        sums = (func.sum(getattr(ModelCallRow, figure)) for figure in Cost.SUMMED)
        query = (
            select(ModelCallRow.resident, func.count(), *sums)
            .where(ModelCallRow.game_id == game_id)
            .group_by(ModelCallRow.resident)
        )
        async with self._sessions() as session:
            rows = (await session.execute(query)).all()
        return {
            caller: Cost(calls=calls, **dict(zip(Cost.SUMMED, summed, strict=True)))
            for caller, calls, *summed in rows
        }

    async def _events(self, query: Select[EventRow]) -> list[Event]:
        async with self._sessions() as session:
            rows = (await session.scalars(query)).all()
        return [
            Event.model_validate(
                {
                    "seq": row.seq,
                    "day": row.day,
                    "phase": row.phase,
                    "visibility": row.visibility,
                    "decision_id": row.decision_id,
                    "payload": row.payload,
                }
            )
            for row in rows
        ]
