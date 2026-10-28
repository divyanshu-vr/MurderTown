"""Every model call has an equivalent cost now, priced from one table.

Revision ID: 0005
Revises: 0004
"""

import sqlalchemy as sa
from alembic import op

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("UPDATE model_calls SET cost_usd = 0 WHERE cost_usd IS NULL")
    with op.batch_alter_table("model_calls") as model_calls:
        model_calls.alter_column("cost_usd", existing_type=sa.Float(), nullable=False)


def downgrade() -> None:
    with op.batch_alter_table("model_calls") as model_calls:
        model_calls.alter_column("cost_usd", existing_type=sa.Float(), nullable=True)
