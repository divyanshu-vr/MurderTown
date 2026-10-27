"""Alembic environment. Expects an open connection from `mm.persistence.migrate.upgrade`."""

from alembic import context

from mm.persistence.tables import Base

connection = context.config.attributes.get("connection")
if connection is None:
    raise RuntimeError("Run migrations through mm.persistence.migrate.upgrade().")

context.configure(connection=connection, target_metadata=Base.metadata, render_as_batch=True)
with context.begin_transaction():
    context.run_migrations()
