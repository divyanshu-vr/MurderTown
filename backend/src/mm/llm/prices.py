"""Equivalent cost: what a model call would cost at the Claude API's list prices.

One table prices every call, whichever provider made it, so a game's cost means
the same thing everywhere. On the Host's subscription the calls cost nothing
extra; equivalent cost is still the fairest measure of how much a game uses.

Haiku 5.5 costs five times as much for a prompt over 100K tokens. MurderTown's
prompts stay far below that, so the table holds only the ordinary price.

The table holds Claude's prices. A Host who plays other vendors' models adds theirs in
`MM_MODEL_PRICES`, as JSON: `{"some-model": {"input": 1.25, "output": 10, "cache_read": 0.125}}`.
"""

from dataclasses import dataclass
from functools import cache

from pydantic_settings import BaseSettings, SettingsConfigDict

from mm.llm.protocol import Usage

MILLION = 1_000_000

FIVE_MINUTE_WRITE = 1.25
"""A cache write that lasts five minutes costs this many times the input price."""

ONE_HOUR_WRITE = 2.0
"""A cache write that lasts an hour costs this many times the input price."""


@dataclass(frozen=True)
class Price:
    """Dollars per million tokens. A cache read has its own price: not every model's is a
    tenth of its input price."""

    input: float
    output: float
    cache_read: float


PRICES = {
    "claude-haiku-5-5": Price(input=0.10, output=0.50, cache_read=0.01),
    "claude-sonnet-5-5": Price(input=2.00, output=10.00, cache_read=0.20),
    "claude-opus-5-5": Price(input=4.00, output=20.00, cache_read=0.20),
    "claude-fable-5-1": Price(input=10.00, output=50.00, cache_read=0.25),
}
"""List prices by full model id, from Anthropic's model pages (checked 2026-10-28)."""


class ModelPrices(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="MM_", env_file=".env", extra="ignore")

    model_prices: dict[str, Price] = {}


@cache
def _configured() -> dict[str, Price]:
    return {**PRICES, **ModelPrices().model_prices}


def price_of(model: str) -> Price:
    """The model's price, or a `ValueError` saying where to add it."""
    prices = _configured()
    if model not in prices:
        raise ValueError(f"No price for {model}: add it to MM_MODEL_PRICES (docs/providers.md)")
    return prices[model]


def equivalent_cost(model: str, usage: Usage) -> float:
    price = price_of(model)
    per_million = (
        usage.input_tokens * price.input
        + usage.output_tokens * price.output
        + usage.cache_read_tokens * price.cache_read
        + usage.cache_write_5m_tokens * price.input * FIVE_MINUTE_WRITE
        + usage.cache_write_1h_tokens * price.input * ONE_HOUR_WRITE
    )
    return per_million / MILLION
