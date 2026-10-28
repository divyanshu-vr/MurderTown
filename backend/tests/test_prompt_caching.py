"""Prompt caching that pays off on the Host's subscription: every Claude Code session a Resident
opens begins the same way, whatever the decision, and caches for five minutes. The briefing that
lists the answer formats is tested in test_prompts.py; why this pays is measured in
docs/agent-sdk-findings.md.
"""

from dataclasses import replace

import pytest
from claude_agent_sdk import ClaudeAgentOptions, ResultMessage

from mm.agents.answers import answer_schema
from mm.engine.decisions import DecisionKind
from tests.claude_sessions import INIT, REQUEST, provider_with

ANSWERED = ResultMessage(
    subtype="success",
    duration_ms=5,
    duration_api_ms=5,
    is_error=False,
    num_turns=2,
    session_id="s",
    usage={"input_tokens": 2},
    structured_output={"urgency": 1, "reason": "a hunch"},
)


async def test_every_session_begins_alike_whatever_the_decision_and_caches_for_five_minutes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    opened: list[ClaudeAgentOptions] = []
    provider = provider_with(monkeypatch, INIT, ANSWERED, opened=opened)

    for kind in (DecisionKind.STATEMENT, DecisionKind.BALLOT):
        await provider.complete(replace(REQUEST, schema=answer_schema(kind)))

    statement, ballot = opened
    assert statement.output_format == ballot.output_format
    assert {options.env.get("CLAUDE_CODE_PROMPT_CACHE_TTL") for options in opened} == {"5m"}
