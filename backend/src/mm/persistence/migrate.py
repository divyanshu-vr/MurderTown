"""Database migrations, run in-process with Alembic.

Migrations always run through `upgrade`, which hands Alembic an open
connection, so the same code works for SQLite in tests and Postgres in production.
"""

from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import Connection
from sqlalchemy.ext.asyncio import AsyncEngine

MIGRATIONS = Path(__file__).parent / "migrations"


async def upgrade(engine: AsyncEngine) -> None:
    """Bring the database schema up to the latest migration."""
    async with engine.begin() as connection:
        await connection.run_sync(_upgrade)


def _upgrade(connection: Connection) -> None:
    config = Config()
    config.set_main_option("script_location", str(MIGRATIONS))
    config.attributes["connection"] = connection
    command.upgrade(config, "head")
