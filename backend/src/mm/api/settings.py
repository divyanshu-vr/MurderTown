"""Backend settings, read from `MM_`-prefixed environment variables or a `.env` file."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="MM_", env_file=".env", extra="ignore")

    database_url: str = "sqlite+aiosqlite:///./runs/murdertown.sqlite3"
    """Docker Postgres in development: postgresql+asyncpg://murdertown:murdertown@localhost:5433/murdertown"""

    cors_origins: list[str] = ["http://localhost:5173"]
