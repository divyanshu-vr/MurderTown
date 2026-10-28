"""Database tables.

Events and model calls are stored exactly as they were written and never changed. The only
row that is ever updated is a game's status once it finishes.
"""

from datetime import datetime
from typing import Any

from sqlalchemy import JSON, DateTime, Float, ForeignKey, Index, Integer, String, Text
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
    __table_args__ = (Index("events_by_decision", "game_id", "decision_id"),)

    game_id: Mapped[str] = mapped_column(ForeignKey("games.id"), primary_key=True)
    seq: Mapped[int] = mapped_column(Integer, primary_key=True)
    day: Mapped[int] = mapped_column(Integer)
    phase: Mapped[str] = mapped_column(String(16))
    type: Mapped[str] = mapped_column(String(32))
    decision_id: Mapped[str | None] = mapped_column(String(32))
    visibility: Mapped[dict[str, Any]] = mapped_column(Json)
    payload: Mapped[dict[str, Any]] = mapped_column(Json)


class ModelCallRow(Base):
    """One attempt at one decision. The columns mirror `ModelCall` field for field."""

    __tablename__ = "model_calls"

    game_id: Mapped[str] = mapped_column(ForeignKey("games.id"), primary_key=True)
    decision_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    attempt: Mapped[int] = mapped_column(Integer, primary_key=True)
    resident: Mapped[str] = mapped_column(String(32))
    kind: Mapped[str] = mapped_column(String(16))
    provider: Mapped[str] = mapped_column(String(32))
    model: Mapped[str] = mapped_column(String(64))
    effort: Mapped[str] = mapped_column(String(16))
    prompt_version: Mapped[str] = mapped_column(String(16))
    system: Mapped[str] = mapped_column(Text)
    prompt: Mapped[str] = mapped_column(Text)
    outcome: Mapped[str] = mapped_column(String(16))
    problem: Mapped[str | None] = mapped_column(Text)
    raw_text: Mapped[str] = mapped_column(Text)
    answer: Mapped[dict[str, Any] | None] = mapped_column(Json)
    input_tokens: Mapped[int] = mapped_column(Integer)
    output_tokens: Mapped[int] = mapped_column(Integer)
    cache_read_tokens: Mapped[int] = mapped_column(Integer)
    cache_write_tokens: Mapped[int] = mapped_column(Integer)
    cost_usd: Mapped[float] = mapped_column(Float)
    latency_ms: Mapped[int] = mapped_column(Integer)
    trace_id: Mapped[str | None] = mapped_column(String(32))
