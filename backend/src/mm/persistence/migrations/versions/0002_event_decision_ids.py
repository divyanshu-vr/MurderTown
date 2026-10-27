"""Link each event to the decision that caused it.

Revision ID: 0002
Revises: 0001
"""

import sqlalchemy as sa
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("events") as events:
        events.add_column(sa.Column("decision_id", sa.String(32), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("events") as events:
        events.drop_column("decision_id")
