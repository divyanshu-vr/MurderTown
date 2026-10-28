"""Keep every model call, so the Mind inspector can show the prompt behind any decision.

Revision ID: 0003
Revises: 0002
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None

Json = sa.JSON().with_variant(postgresql.JSONB(), "postgresql")


def upgrade() -> None:
    op.create_table(
        "model_calls",
        sa.Column("game_id", sa.String(32), sa.ForeignKey("games.id"), primary_key=True),
        sa.Column("decision_id", sa.String(32), primary_key=True),
        sa.Column("attempt", sa.Integer, primary_key=True),
        sa.Column("resident", sa.String(32), nullable=False),
        sa.Column("kind", sa.String(16), nullable=False),
        sa.Column("provider", sa.String(32), nullable=False),
        sa.Column("model", sa.String(64), nullable=False),
        sa.Column("effort", sa.String(16), nullable=False),
        sa.Column("prompt_version", sa.String(16), nullable=False),
        sa.Column("system", sa.Text, nullable=False),
        sa.Column("prompt", sa.Text, nullable=False),
        sa.Column("outcome", sa.String(16), nullable=False),
        sa.Column("problem", sa.Text, nullable=True),
        sa.Column("raw_text", sa.Text, nullable=False),
        sa.Column("answer", Json, nullable=True),
        sa.Column("input_tokens", sa.Integer, nullable=False),
        sa.Column("output_tokens", sa.Integer, nullable=False),
        sa.Column("cache_read_tokens", sa.Integer, nullable=False),
        sa.Column("cache_write_tokens", sa.Integer, nullable=False),
        sa.Column("cost_usd", sa.Float, nullable=True),
        sa.Column("latency_ms", sa.Integer, nullable=False),
    )
    op.create_index("events_by_decision", "events", ["game_id", "decision_id"])


def downgrade() -> None:
    op.drop_index("events_by_decision", table_name="events")
    op.drop_table("model_calls")
