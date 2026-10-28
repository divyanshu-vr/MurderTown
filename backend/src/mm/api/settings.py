"""Backend settings, read from `MM_`-prefixed environment variables or a `.env` file."""

from pydantic_settings import BaseSettings, SettingsConfigDict

from mm.agents.llm_brain import ATTEMPTS
from mm.llm import CALL_TIMEOUT_S


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="MM_", env_file=".env", extra="ignore")

    database_url: str = "sqlite+aiosqlite:///./runs/murdertown.sqlite3"
    """Docker Postgres in development: postgresql+asyncpg://murdertown:murdertown@localhost:5433/murdertown"""

    cors_origins: list[str] = ["http://localhost:5173"]

    resume_on_boot: bool = True
    """Resume, at start-up, every game the server left running."""

    shutdown_grace_seconds: float = ATTEMPTS * CALL_TIMEOUT_S + 20
    """How long a shutdown waits for decisions already asked: each may take every attempt."""
