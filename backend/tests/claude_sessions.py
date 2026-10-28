"""Fake Claude Code sessions, for testing the Claude Agent SDK provider with no Claude login."""

from collections.abc import AsyncIterator

import pytest
from claude_agent_sdk import ClaudeAgentOptions, SystemMessage

from mm.llm import Effort, ModelRequest
from mm.llm import claude_agent_sdk as sdk

INIT = SystemMessage(
    subtype="init",
    data={"apiKeySource": "none", "tools": ["StructuredOutput"], "mcp_servers": [], "model": "m"},
)

REQUEST = ModelRequest(
    system="s", memory="m", task="t", schema={}, model="claude-haiku-5-5", effort=Effort.LOW
)


def provider_with(
    monkeypatch: pytest.MonkeyPatch,
    *messages: object,
    then: Exception | None = None,
    opened: list[ClaudeAgentOptions] | None = None,
) -> sdk.ClaudeAgentSDKProvider:
    """A provider whose sessions yield `messages` and then raise `then`, with no Claude login.
    Each session's options are added to `opened`, if given."""

    async def session(*, prompt: str, options: ClaudeAgentOptions) -> AsyncIterator[object]:
        if opened is not None:
            opened.append(options)
        for message in messages:
            yield message
        if then:
            raise then

    monkeypatch.setattr(sdk, "claude_cli", lambda: "claude")
    monkeypatch.setattr(sdk, "require_subscription_login", lambda cli: None)
    monkeypatch.setattr(sdk, "query", session)
    return sdk.ClaudeAgentSDKProvider(concurrency=1)
