"""Keep how many of a call's cache writes last an hour, so a replayed call costs the same.

Revision ID: 0007
Revises: 0006
"""

import sqlalchemy as sa
from alembic import op

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("model_calls") as model_calls:
        model_calls.add_column(
            sa.Column("cache_write_1h_tokens", sa.Integer(), nullable=False, server_default="0")
        )


def downgrade() -> None:
    with op.batch_alter_table("model_calls") as model_calls:
        model_calls.drop_column("cache_write_1h_tokens")
