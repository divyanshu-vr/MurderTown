"""Games and their event logs.

Revision ID: 0001
Revises:
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None

Json = sa.JSON().with_variant(postgresql.JSONB(), "postgresql")


def upgrade() -> None:
    op.create_table(
        "games",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("config", Json, nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("winner", sa.String(16), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "events",
        sa.Column("game_id", sa.String(32), sa.ForeignKey("games.id"), primary_key=True),
        sa.Column("seq", sa.Integer, primary_key=True),
        sa.Column("day", sa.Integer, nullable=False),
        sa.Column("phase", sa.String(16), nullable=False),
        sa.Column("type", sa.String(32), nullable=False),
        sa.Column("visibility", Json, nullable=False),
        sa.Column("payload", Json, nullable=False),
    )


def downgrade() -> None:
    op.drop_table("events")
    op.drop_table("games")
