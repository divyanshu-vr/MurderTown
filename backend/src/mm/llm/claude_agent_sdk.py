"""Claude through the Claude Agent SDK, on the Host's Claude subscription (no API key).

Each call is one fresh, isolated Claude Code session that can do nothing but
answer: no built-in tools, no MCP servers, no settings, CLAUDE.md, memory,
attachments or saved history, and an empty working directory. The prompt is
delivered verbatim, so text another Resident wrote can never expand into a
file read. Every call checks, from the session's own report, that it ran on
the subscription and loaded nothing it should not have.

Anthropic's terms allow subscription use for the subscriber's own, ordinary
use only, so this provider is for games the Host runs and watches themselves.
"""

import asyncio
import json
import os
import shutil
import subprocess
import tempfile
import time
from collections.abc import AsyncGenerator
from contextlib import aclosing
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, cast

import claude_agent_sdk
from claude_agent_sdk import (
    AssistantMessage,
    ClaudeAgentOptions,
    Message,
    ResultMessage,
    SystemMessage,
    query,
)

from mm.llm.protocol import ModelReply, ModelRequest, Usage

ISOLATION_ENV = {
    "CLAUDE_CODE_DISABLE_CLAUDE_MDS": "1",
    "CLAUDE_CODE_DISABLE_AUTO_MEMORY": "1",
    "ENABLE_CLAUDEAI_MCP_SERVERS": "false",
    "CLAUDE_CODE_DISABLE_ATTACHMENTS": "1",
    "CLAUDE_CODE_SKIP_PROMPT_HISTORY": "1",
    "CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC": "1",
}
"""Switches that keep the Host's own Claude Code setup out of every Agent's context."""

ALLOWED_TOOLS = {"StructuredOutput"}
"""The only tool a session may have: the SDK's own carrier for the structured answer."""

API_CREDENTIALS = ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN")


class SubscriptionError(RuntimeError):
    """Live games would not run on the Host's subscription, so they must not run at all."""


@dataclass(frozen=True)
class SessionFacts:
    """What a session reported about itself when it started."""

    api_key_source: str
    tools: tuple[str, ...]
    mcp_servers: tuple[str, ...]
    model: str


def claude_cli() -> str:
    """The Claude Code executable the SDK will run: its bundled copy, or one on PATH."""
    executable = "claude.exe" if os.name == "nt" else "claude"
    bundled = Path(claude_agent_sdk.__file__).parent / "_bundled" / executable
    if bundled.is_file():
        return str(bundled)
    found = shutil.which("claude")
    if found is None:
        raise SubscriptionError("Claude Code is not installed, so there is no subscription login.")
    return found


def require_subscription_login(cli: str) -> None:
    """Refuse to start unless calls will be billed to the Host's claude.ai subscription."""
    for name in API_CREDENTIALS:
        if os.environ.get(name):
            raise SubscriptionError(
                f"{name} is set, so calls would be billed to the API. Unset it to play on the "
                "subscription."
            )
    result = subprocess.run(
        [cli, "auth", "status"], capture_output=True, text=True, timeout=60, check=False
    )
    try:
        status = json.loads(result.stdout)
    except json.JSONDecodeError as error:
        message = f"Could not read the Claude login status: {result.stderr}"
        raise SubscriptionError(message) from error
    if not status.get("loggedIn") or status.get("authMethod") != "claude.ai":
        raise SubscriptionError(
            "Claude Code is not logged in with a claude.ai subscription. Run `claude auth login`."
        )


class ClaudeAgentSDKProvider:
    name = "claude-agent-sdk"

    def __init__(self, *, concurrency: int = 5, timeout_s: float = 90.0) -> None:
        self.cli = claude_cli()
        require_subscription_login(self.cli)
        self.sandbox = Path(tempfile.gettempdir()) / "murdertown-agent-sandbox"
        self.sandbox.mkdir(exist_ok=True)
        self.timeout_s = timeout_s
        self._slots = asyncio.Semaphore(concurrency)
        self.last_session: SessionFacts | None = None

    async def complete(self, request: ModelRequest) -> ModelReply:
        async with self._slots:
            started = time.monotonic()
            try:
                async with asyncio.timeout(self.timeout_s):
                    reply = await self._ask(request)
            except TimeoutError:
                reply = ModelReply(
                    outcome="timeout",
                    data=None,
                    text="",
                    error=f"no answer within {self.timeout_s:.0f} seconds",
                )
            return replace(reply, latency_ms=int((time.monotonic() - started) * 1000))

    def _options(self, request: ModelRequest) -> ClaudeAgentOptions:
        return ClaudeAgentOptions(
            system_prompt=request.system,
            tools=[],
            setting_sources=[],
            strict_mcp_config=True,
            skills=[],
            permission_mode="dontAsk",
            model=request.model,
            effort=request.effort.value,
            output_format={"type": "json_schema", "schema": dict(request.schema)},
            max_turns=3,
            cwd=str(self.sandbox),
            cli_path=self.cli,
            verbatim_prompts=True,
            extra_args={"no-session-persistence": None},
            env=ISOLATION_ENV,
        )

    async def _ask(self, request: ModelRequest) -> ModelReply:
        """One session: closing the message stream on any exit also ends the subprocess."""
        result: ResultMessage | None = None
        isolation: str | None = None
        model_error: str | None = None
        # query() is an async generator; closing it also ends the Claude Code subprocess.
        messages = cast(
            AsyncGenerator[Message], query(prompt=request.prompt, options=self._options(request))
        )
        async with aclosing(messages) as stream:
            async for message in stream:
                if isinstance(message, SystemMessage) and message.subtype == "init":
                    self.last_session = _session_facts(message.data)
                    isolation = _isolation_problem(self.last_session)
                    if isolation:
                        break
                elif isinstance(message, AssistantMessage) and message.error:
                    model_error = f"the model call failed: {message.error}"
                elif isinstance(message, ResultMessage):
                    result = message
        if isolation:
            raise SubscriptionError(isolation)
        if result is None:
            return ModelReply(outcome="error", data=None, text="", error=model_error or "no result")
        return _reply_from(result, model_error)


def _session_facts(data: dict[str, Any]) -> SessionFacts:
    servers = data.get("mcp_servers") or []
    return SessionFacts(
        api_key_source=str(data.get("apiKeySource", "")),
        tools=tuple(data.get("tools") or ()),
        mcp_servers=tuple(str(server.get("name", server)) for server in servers),
        model=str(data.get("model", "")),
    )


def _isolation_problem(session: SessionFacts) -> str | None:
    if session.api_key_source != "none":
        source = session.api_key_source
        return f"isolation check failed: the session used an API credential ({source})"
    if extra := set(session.tools) - ALLOWED_TOOLS:
        return f"isolation check failed: the session loaded tools {sorted(extra)}"
    if session.mcp_servers:
        return f"isolation check failed: the session loaded MCP servers {list(session.mcp_servers)}"
    return None


def _reply_from(result: ResultMessage, problem: str | None) -> ModelReply:
    usage = result.usage or {}
    tokens = Usage(
        input_tokens=int(usage.get("input_tokens", 0)),
        output_tokens=int(usage.get("output_tokens", 0)),
        cache_read_tokens=int(usage.get("cache_read_input_tokens", 0)),
        cache_write_tokens=int(usage.get("cache_creation_input_tokens", 0)),
    )
    reply = ModelReply(
        outcome="ok",
        data=_structured(result),
        text=result.result or "",
        usage=tokens,
        cost_usd=result.total_cost_usd,
    )
    if result.stop_reason == "refusal":
        return replace(reply, outcome="refusal", data=None, error="the model declined to answer")
    if result.is_error or result.subtype != "success":
        detail = problem or "; ".join(result.errors or []) or result.subtype
        return replace(reply, outcome="error", data=None, error=detail)
    return reply


def _structured(result: ResultMessage) -> dict[str, Any] | None:
    """The structured answer, or the result text parsed as JSON if the SDK did not supply one."""
    if isinstance(result.structured_output, dict):
        return result.structured_output
    try:
        parsed = json.loads(result.result or "")
    except json.JSONDecodeError:
        return None
    return parsed if isinstance(parsed, dict) else None
