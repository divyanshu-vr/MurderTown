"""Opt-in live checks of the Claude Agent SDK provider, on the Host's Claude subscription.

Skipped unless MM_LIVE_TESTS=1. A full run makes four Claude Haiku calls.
"""

import os

import pytest

from mm.agents.answers import answer_schema, read_answer
from mm.engine import GameConfig, PlayedBy
from mm.engine.decisions import DecisionKind, Statement
from mm.llm import ModelRequest
from mm.llm.prices import equivalent_cost
from tests.prompt_spy import Shown, spy_on

pytestmark = pytest.mark.skipif(
    os.environ.get("MM_LIVE_TESTS") != "1",
    reason="makes real calls on the Claude subscription; set MM_LIVE_TESTS=1 to run",
)


async def first_two_decisions() -> tuple[Shown, Shown]:
    """One Resident's first Statement and the ballot they cast next."""
    shown, _ = await spy_on(GameConfig(residents=8, murderers=2, max_days=1, seed=31))
    statement = next(s for s in shown if s.request.kind is DecisionKind.STATEMENT)
    ballot = next(
        s
        for s in shown
        if s.request.kind is DecisionKind.BALLOT and s.resident == statement.resident
    )
    return statement, ballot


def request_for(seen: Shown) -> ModelRequest:
    played_by = PlayedBy()
    return ModelRequest(
        system=seen.prompt.system,
        memory=seen.prompt.memory,
        task=seen.prompt.task,
        schema=answer_schema(seen.request.kind),
        model=played_by.model,
        effort=played_by.effort,
    )


async def test_an_isolated_session_answers_on_the_subscription_and_caches_its_prompt() -> None:
    from mm.llm.claude_agent_sdk import ClaudeAgentSDKProvider  # checks the login on creation

    statement, _ = await first_two_decisions()
    provider = ClaudeAgentSDKProvider(concurrency=1)

    first = await provider.complete(request_for(statement))
    repeat = await provider.complete(request_for(statement))

    assert first.outcome == "ok", first.error
    assert isinstance(read_answer(statement.request, first.data, statement.role), Statement)
    session = provider.last_session
    assert session is not None
    assert session.api_key_source == "none"
    assert session.tools == ("StructuredOutput",)
    assert session.mcp_servers == ()
    assert repeat.usage.cache_read_tokens > 0
    for name, reply in (("first", first), ("repeat", repeat)):
        cost = equivalent_cost(PlayedBy().model, reply.usage)
        print(f"\n{name}: {reply.latency_ms} ms, {reply.usage}, ${cost:.6f}")


@pytest.mark.xfail(
    strict=True,
    reason=(
        "Each decision is a fresh Claude Code session that caches its whole prompt, so an "
        "Agent's next decision, with the same briefing but a new task, finds nothing to reuse. "
        "Measured in docs/agent-sdk-findings.md; ticket #21 makes caching pay off."
    ),
)
async def test_an_agents_next_decision_reads_its_briefing_from_the_cache() -> None:
    from mm.llm.claude_agent_sdk import ClaudeAgentSDKProvider

    statement, ballot = await first_two_decisions()
    provider = ClaudeAgentSDKProvider(concurrency=1)

    await provider.complete(request_for(statement))
    next_decision = await provider.complete(request_for(ballot))

    assert next_decision.outcome == "ok", next_decision.error
    assert next_decision.usage.cache_read_tokens > 0
