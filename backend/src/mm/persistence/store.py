"""The game store: where games, their event logs and their model calls are kept."""

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Literal, cast
from uuid import uuid4

from sqlalchemy import Select, and_, func, select, text, update
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker

from mm.agents import Cost, ModelCall
from mm.engine import GameConfig, Phase, Side
from mm.engine.events import Event
from mm.persistence.tables import EventRow, GameRow, ModelCallRow

GameStatus = Literal["running", "paused", "finished", "aborted", "failed"]
"""A game is paused by the Host. It is aborted when the model gave no answer; it failed when
the game itself crashed."""

UNFINISHED: tuple[GameStatus, ...] = ("running", "paused")


@dataclass(frozen=True)
class StoredGame:
    """A game at a glance: where it stands now, and what its model calls have cost."""

    id: str
    config: GameConfig
    status: GameStatus
    winner: Side | None
    created_at: datetime
    last_seq: int
    day: int
    phase: Phase
    cost_usd: float


_last = (
    select(EventRow.game_id, func.max(EventRow.seq).label("seq"))
    .group_by(EventRow.game_id)
    .subquery()
)
_cost = (
    select(ModelCallRow.game_id, func.sum(ModelCallRow.cost_usd).label("cost_usd"))
    .group_by(ModelCallRow.game_id)
    .subquery()
)
_Glance = Select[GameRow, int | None, int | None, str | None, float | None]
_GLANCE: _Glance = (
    select(GameRow, _last.c.seq, EventRow.day, EventRow.phase, _cost.c.cost_usd)
    .outerjoin(_last, _last.c.game_id == GameRow.id)
    .outerjoin(EventRow, and_(EventRow.game_id == GameRow.id, EventRow.seq == _last.c.seq))
    .outerjoin(_cost, _cost.c.game_id == GameRow.id)
)
"""Each game with the Day and Phase its latest event was stamped with, and what it cost."""


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

    async def set_paused(self, game_id: str, paused: bool) -> None:
        """Mark a game paused, or running again, unless it has ended meanwhile."""
        status: GameStatus = "paused" if paused else "running"
        unfinished = GameRow.status.in_(UNFINISHED)
        async with self._sessions.begin() as session:
            await session.execute(
                update(GameRow).where(GameRow.id == game_id, unfinished).values(status=status)
            )

    async def game(self, game_id: str) -> StoredGame | None:
        found = await self._at_a_glance(_GLANCE.where(GameRow.id == game_id))
        return found[0] if found else None

    async def games(self, limit: int) -> list[StoredGame]:
        """The latest games, newest first."""
        return await self._at_a_glance(_GLANCE.order_by(GameRow.created_at.desc()).limit(limit))

    async def _at_a_glance(self, query: _Glance) -> list[StoredGame]:
        async with self._sessions() as session:
            rows = (await session.execute(query)).all()
        return [
            StoredGame(
                id=game.id,
                config=GameConfig.model_validate(game.config),
                status=cast(GameStatus, game.status),
                winner=Side(game.winner) if game.winner else None,
                created_at=game.created_at.replace(tzinfo=game.created_at.tzinfo or UTC),
                last_seq=last_seq or 0,
                day=day or 0,
                phase=Phase(phase) if phase else Phase.SETUP,
                cost_usd=cost_usd or 0.0,
            )
            for game, last_seq, day, phase, cost_usd in rows
        ]

    async def unfinished(self) -> list[StoredGame]:
        """Games running or paused: the server stopped before they ended."""
        return await self._at_a_glance(_GLANCE.where(GameRow.status.in_(UNFINISHED)))

    async def events(
        self, game_id: str, after: int = 0, limit: int | None = None, public: bool = False
    ) -> list[Event]:
        """A game's events with a sequence number above `after`, oldest first. With `public`, only
        those the whole town perceived (`Visibility.public`), chosen here so pages stay full."""
        query = select(EventRow).where(EventRow.game_id == game_id, EventRow.seq > after)
        if public:
            query = query.where(EventRow.visibility["scope"].as_string() == "everyone")
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
