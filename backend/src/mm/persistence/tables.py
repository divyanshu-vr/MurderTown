"""Database tables.

Events are stored exactly as they were appended and never changed. The only
row that is ever updated is a game's status once it finishes.
"""

from datetime import datetime
from typing import Any

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

Json = JSON().with_variant(JSONB(), "postgresql")


class Base(DeclarativeBase):
    pass


class GameRow(Base):
    __tablename__ = "games"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    config: Mapped[dict[str, Any]] = mapped_column(Json)
    status: Mapped[str] = mapped_column(String(16))
    winner: Mapped[str | None] = mapped_column(String(16))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class EventRow(Base):
    __tablename__ = "events"

    game_id: Mapped[str] = mapped_column(ForeignKey("games.id"), primary_key=True)
    seq: Mapped[int] = mapped_column(Integer, primary_key=True)
    day: Mapped[int] = mapped_column(Integer)
    phase: Mapped[str] = mapped_column(String(16))
    type: Mapped[str] = mapped_column(String(32))
    visibility: Mapped[dict[str, Any]] = mapped_column(Json)
    payload: Mapped[dict[str, Any]] = mapped_column(Json)
