"""Claude through the Anthropic API, for a Host with an API key.

It sends the same prompts as every provider. The system briefing and the Resident's
memory each carry a cache breakpoint, so a Resident's later decisions read them from the
cache while their memory is unchanged; the task, new every time, is never cached.
"""

import json
from typing import Any, Literal

import anthropic
import httpx2
from anthropic.types import (
    CacheControlEphemeralParam,
    JSONOutputFormatParam,
    Message,
    MessageParam,
    OutputConfigParam,
    TextBlockParam,
)

from mm.engine import Effort
from mm.llm.calling import CallLimits
from mm.llm.protocol import CALL_TIMEOUT_S, ModelReply, ModelRequest, Usage

MAX_TOKENS = 8192
"""Room for the answer and for the thinking current models always do before it."""

EFFORTS: dict[Effort, Literal["low", "medium", "high", "max"]] = {
    Effort.LOW: "low",
    Effort.MEDIUM: "medium",
    Effort.HIGH: "high",
    Effort.MAX: "max",
}


def _text(text: str, cached: bool = False) -> TextBlockParam:
    block = TextBlockParam(type="text", text=text)
    if cached:
        block["cache_control"] = CacheControlEphemeralParam(type="ephemeral")
    return block


class AnthropicAPIProvider:
    name = "anthropic-api"

    def __init__(
        self,
        api_key: str,
        *,
        concurrency: int = 5,
        timeout_s: float = CALL_TIMEOUT_S,
        max_retries: int = 2,
        http_client: httpx2.AsyncClient | None = None,
    ) -> None:
        self.limits = CallLimits(concurrency, timeout_s)
        self.client = anthropic.AsyncAnthropic(
            api_key=api_key,
            max_retries=max_retries,
            http_client=http_client,
            open_telemetry=False,  # the game traces every call itself, once
        )

    async def complete(self, request: ModelRequest) -> ModelReply:
        return await self.limits.run(lambda: self._ask(request))

    async def _ask(self, request: ModelRequest) -> ModelReply:
        try:
            message = await self.client.messages.create(
                model=request.model,
                max_tokens=MAX_TOKENS,
                system=[_text(request.system, cached=True)],
                messages=[_asked(request)],
                output_config=OutputConfigParam(
                    effort=EFFORTS[request.effort],
                    format=JSONOutputFormatParam(type="json_schema", schema=dict(request.schema)),
                ),
            )
        except anthropic.APITimeoutError as error:
            return ModelReply.failure(str(error), outcome="timeout")
        except anthropic.APIError as error:
            return ModelReply.failure(str(error))
        return _reply_from(message)


def _asked(request: ModelRequest) -> MessageParam:
    """The memory, cached, then the task. The API rejects an empty block, and a recap has no
    memory of its own, so an empty memory is left out."""
    memory = [_text(request.memory, cached=True)] if request.memory else []
    asked: MessageParam = {"role": "user", "content": [*memory, _text(request.task)]}
    return asked


def _reply_from(message: Message) -> ModelReply:
    text = "".join(block.text for block in message.content if block.type == "text")
    usage = message.usage
    writes = usage.cache_creation
    tokens = Usage(
        input_tokens=usage.input_tokens,
        output_tokens=usage.output_tokens,
        cache_read_tokens=usage.cache_read_input_tokens or 0,
        cache_write_5m_tokens=writes.ephemeral_5m_input_tokens if writes else 0,
        cache_write_1h_tokens=writes.ephemeral_1h_input_tokens if writes else 0,
    )
    if message.stop_reason == "refusal":
        return ModelReply(
            outcome="refusal", data=None, text=text, usage=tokens, error="the model declined"
        )
    return ModelReply(outcome="ok", data=_parsed(text), text=text, usage=tokens)


def _parsed(text: str) -> dict[str, Any] | None:
    """The answer as JSON, or None if it is not a JSON object (the pipeline then says so)."""
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        return None
    return parsed if isinstance(parsed, dict) else None
