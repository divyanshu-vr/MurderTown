"""Widen a model call's decision kind: "conversation_message" is longer than 16 characters.

Postgres enforces the width (SQLite does not), so recording a Conversation's model call failed.

Revision ID: 0006
Revises: 0005
"""

import sqlalchemy as sa
from alembic import op

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("model_calls") as model_calls:
        model_calls.alter_column("kind", existing_type=sa.String(16), type_=sa.String(32))


def downgrade() -> None:
    with op.batch_alter_table("model_calls") as model_calls:
        model_calls.alter_column("kind", existing_type=sa.String(32), type_=sa.String(16))
