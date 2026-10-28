"""Backend settings, read from `MM_`-prefixed environment variables or a `.env` file."""

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

from mm.agents.llm_brain import ATTEMPTS
from mm.llm import CALL_TIMEOUT_S
from mm.llm.providers import PROVIDERS_WITH_KEYS, Providers


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="MM_", env_file=".env", extra="ignore")

    database_url: str = "sqlite+aiosqlite:///./runs/murdertown.sqlite3"
    """Docker Postgres in development: postgresql+asyncpg://murdertown:murdertown@localhost:5433/murdertown"""

    cors_origins: list[str] = ["http://localhost:5173"]

    host_token: SecretStr | None = None
    """Proves a request comes from the Host, who alone may start and control games and see a
    game's full scope. The server will not start without one; `mm serve` makes one if need be."""

    new_games_per_hour: int = Field(default=12, ge=1)
    """How many games the Host may start in any hour: it bounds what a leaked token can cost."""

    anthropic_api_key: SecretStr | None = None
    """With it, "claude" in a lineup plays on the Anthropic API instead of the subscription."""
    openai_api_key: SecretStr | None = None
    openrouter_api_key: SecretStr | None = None
    gemini_api_key: SecretStr | None = None
    xai_api_key: SecretStr | None = None

    resume_on_boot: bool = True
    """Resume, at start-up, every game the server left running."""

    shutdown_grace_seconds: float = ATTEMPTS * CALL_TIMEOUT_S + 20
    """How long a shutdown waits for decisions already asked: each may take every attempt."""

    def providers(self, concurrency: int = 5) -> Providers:
        """The model providers these settings can reach, each made when a game first needs it,
        and each letting `concurrency` calls run at once."""
        keys = {
            name: secret.get_secret_value()
            for name in PROVIDERS_WITH_KEYS
            if (secret := getattr(self, f"{name}_api_key"))
        }
        return Providers(keys, concurrency)
