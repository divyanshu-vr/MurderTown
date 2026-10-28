"""Keep each model call's trace id, so the Mind inspector can link to the trace.

Revision ID: 0004
Revises: 0003
"""

import sqlalchemy as sa
from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("model_calls") as model_calls:
        model_calls.add_column(sa.Column("trace_id", sa.String(32), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("model_calls") as model_calls:
        model_calls.drop_column("trace_id")
