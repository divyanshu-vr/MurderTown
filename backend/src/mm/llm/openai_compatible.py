"""OpenAI, OpenRouter, Gemini and xAI, which all speak OpenAI's chat completions API.

One client serves them all; only the base URL, the key and a few request options
differ. The answer is asked for in the decision's JSON schema, at the Resident's
effort. A server that refuses either option for a model (not every model reasons,
and not every server enforces schemas) is asked again without it, and the provider
remembers, so later calls to that model ask once. Without the schema option, the
schema is written into the prompt and the JSON read from the text; the pipeline
checks the answer either way. A call's record keeps the effort and briefing the game
asked for, not what a server was finally sent.
"""

import json
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any

import httpx2
import openai
from openai.types.chat import ChatCompletion, ChatCompletionMessageParam

from mm.llm.calling import CallLimits
from mm.llm.protocol import CALL_TIMEOUT_S, ModelReply, ModelRequest, Usage, json_object

OPTIONAL = ("response_format", "reasoning_effort")
"""Request options a server may refuse for a model, so they can be dropped."""


@dataclass(frozen=True)
class Vendor:
    base_url: str | None
    """None for OpenAI itself, the client's default."""
    extra_body: dict[str, Any] = field(default_factory=dict)


VENDORS = {
    "openai": Vendor(base_url=None),
    "openrouter": Vendor(
        base_url="https://openrouter.ai/api/v1",
        # route only to providers that honour every option, the JSON schema included
        extra_body={"provider": {"require_parameters": True}},
    ),
    "gemini": Vendor(base_url="https://generativelanguage.googleapis.com/v1beta/openai/"),
    "xai": Vendor(base_url="https://api.x.ai/v1"),
}


class OpenAICompatibleProvider:
    def __init__(
        self,
        name: str,
        vendor: Vendor,
        api_key: str,
        *,
        concurrency: int = 5,
        timeout_s: float = CALL_TIMEOUT_S,
        max_retries: int = 2,
        http_client: httpx2.AsyncClient | None = None,
    ) -> None:
        self.name, self.vendor = name, vendor
        self.limits = CallLimits(concurrency, timeout_s)
        self.client = openai.AsyncOpenAI(
            api_key=api_key,
            base_url=vendor.base_url,
            max_retries=max_retries,
            http_client=http_client,
        )
        self.refused: defaultdict[str, set[str]] = defaultdict(set)
        """The options each model's server refused."""

    @classmethod
    def for_vendor(cls, name: str, api_key: str, **options: Any) -> "OpenAICompatibleProvider":
        return cls(name, VENDORS[name], api_key, **options)

    async def complete(self, request: ModelRequest) -> ModelReply:
        return await self.limits.run(lambda: self._reply(request))

    async def _reply(self, request: ModelRequest) -> ModelReply:
        try:
            return _reply_from(await self._completion(request))
        except openai.APITimeoutError as error:
            return ModelReply.failure(str(error), outcome="timeout")
        except openai.APIError as error:
            return ModelReply.failure(str(error))

    async def _completion(self, request: ModelRequest) -> ChatCompletion:
        """Ask, dropping each option the model's server refuses until it answers."""
        refused = self.refused[request.model]
        while True:
            try:
                return await self._ask(request, refused)
            except (openai.BadRequestError, openai.NotFoundError) as error:
                option = _refused_option(error, refused)
                if option is None:
                    raise
                refused.add(option)

    async def _ask(self, request: ModelRequest, refused: set[str]) -> ChatCompletion:
        system = request.system
        options: dict[str, Any] = {}
        if "response_format" in refused:
            schema = json.dumps(request.schema)
            system += f"\n\nAnswer with one JSON object matching this JSON Schema: {schema}"
        else:
            options["response_format"] = {
                "type": "json_schema",
                "json_schema": {"name": "answer", "schema": dict(request.schema), "strict": True},
            }
        if "reasoning_effort" not in refused:
            options["reasoning_effort"] = request.effort.value
        messages: list[ChatCompletionMessageParam] = [
            {"role": "system", "content": system},
            {"role": "user", "content": request.prompt},
        ]
        completion: ChatCompletion = await self.client.chat.completions.create(
            model=request.model,
            messages=messages,
            extra_body=self.vendor.extra_body or None,
            **options,
        )
        return completion


def _refused_option(error: openai.APIStatusError, refused: set[str]) -> str | None:
    """The option a server refused, if the error names one not yet dropped. OpenRouter says it
    found no endpoint able to honour the options, without naming one: the schema goes first."""
    message = str(error)
    for option in OPTIONAL:
        if option not in refused and option in message:
            return option
    no_endpoint = isinstance(error, openai.NotFoundError) and "endpoints" in message.lower()
    return (
        next((option for option in OPTIONAL if option not in refused), None)
        if no_endpoint
        else None
    )


def _reply_from(completion: ChatCompletion) -> ModelReply:
    choice = completion.choices[0]
    message = choice.message
    usage = completion.usage
    details = usage.prompt_tokens_details if usage else None
    cached = (details.cached_tokens or 0) if details else 0
    tokens = Usage(
        input_tokens=(usage.prompt_tokens if usage else 0) - cached,
        output_tokens=usage.completion_tokens if usage else 0,
        cache_read_tokens=cached,
    )
    text = message.content or ""
    if message.refusal or choice.finish_reason == "content_filter":
        declined = "the model declined"
        return ModelReply(
            outcome="refusal", data=None, text=message.refusal or text, usage=tokens, error=declined
        )
    return ModelReply(outcome="ok", data=json_object(text), text=text, usage=tokens)
