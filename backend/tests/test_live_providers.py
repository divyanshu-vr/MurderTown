"""Opt-in live checks of the paid-API providers, one small call each.

Skipped unless MM_LIVE_TESTS=1 and the provider's key is set in the environment or
backend/.env (see docs/providers.md). The Anthropic API uses Claude Haiku; the others
use the model named in MM_LIVE_<PROVIDER>_MODEL, which must also have a price
(MM_MODEL_PRICES).
"""

import os

import pytest

from mm.agents.answers import answer_schema
from mm.api.settings import Settings
from mm.engine.decisions import Bid, DecisionKind
from mm.llm import Effort, ModelRequest
from mm.llm.providers import PROVIDERS_WITH_KEYS

pytestmark = pytest.mark.skipif(
    os.environ.get("MM_LIVE_TESTS") != "1",
    reason="makes paid API calls; set MM_LIVE_TESTS=1 (and the provider's key) to run",
)

DEFAULT_MODELS = {"anthropic": "claude-haiku-5-5"}


@pytest.mark.parametrize("name", PROVIDERS_WITH_KEYS)
async def test_a_paid_provider_answers_a_bid_in_its_schema(name: str) -> None:
    settings = Settings()
    if getattr(settings, f"{name}_api_key") is None:
        pytest.skip(f"no MM_{name.upper()}_API_KEY")
    model = os.environ.get(f"MM_LIVE_{name.upper()}_MODEL", DEFAULT_MODELS.get(name))
    if model is None:
        pytest.skip(f"no MM_LIVE_{name.upper()}_MODEL")

    reply = await settings.providers()[name].complete(
        ModelRequest(
            system="You are a Resident of a small town, playing a party game of hidden roles.",
            memory="",
            task="Say how urgently you want to speak next, from 0 (listen) to 4, and why.",
            schema=answer_schema(DecisionKind.BID),
            model=model,
            effort=Effort.LOW,
        )
    )

    assert reply.outcome == "ok", reply.error
    assert 0 <= Bid.model_validate(reply.data).urgency <= 4
