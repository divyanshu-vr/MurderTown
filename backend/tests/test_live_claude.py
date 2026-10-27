"""Opt-in live check of the Claude Agent SDK provider, on the Host's Claude subscription.

Skipped unless MM_LIVE_TESTS=1. One run makes two Claude Haiku calls.
"""

import os

import pytest

from mm.agents.answers import answer_schema, read_answer
from mm.engine import GameConfig
from mm.engine.decisions import DecisionKind, Statement
from mm.llm import ModelRequest
from tests.test_prompts import spy_on

pytestmark = pytest.mark.skipif(
    os.environ.get("MM_LIVE_TESTS") != "1",
    reason="makes real calls on the Claude subscription; set MM_LIVE_TESTS=1 to run",
)


async def test_an_isolated_session_answers_on_the_subscription_and_reuses_the_cache() -> None:
    from mm.llm.claude_agent_sdk import ClaudeAgentSDKProvider  # checks the login on creation

    shown, _ = await spy_on(GameConfig(residents=8, murderers=2, max_days=1, seed=31))
    first_statement = next(s for s in shown if s.request.kind is DecisionKind.STATEMENT)
    request = ModelRequest(
        system=first_statement.prompt.system,
        prompt=first_statement.prompt.user_message(),
        schema=answer_schema(DecisionKind.STATEMENT),
        model="claude-haiku-5-5",
        effort="low",
    )
    provider = ClaudeAgentSDKProvider(concurrency=1)

    first = await provider.complete(request)
    second = await provider.complete(request)

    assert first.outcome == "ok", first.error
    assert isinstance(read_answer(first_statement.request, first.data), Statement)
    session = provider.last_session
    assert session is not None
    assert session.api_key_source == "none"
    assert session.tools == ("StructuredOutput",)
    assert session.mcp_servers == ()
    assert first.usage.input_tokens + first.usage.cache_write_tokens > 0
    assert second.usage.cache_read_tokens > 0
    print(f"\nfirst: {first.latency_ms} ms, {first.usage}, ${first.cost_usd}")
    print(f"second: {second.latency_ms} ms, {second.usage}, ${second.cost_usd}")
    print(f"answer: {first.data}")
