"""The model providers a Host can use, by the names a game's lineup gives them.

Each is made the first time a game asks for it, so the subscription's login is
checked only when a game is played on it. `"claude"` is the Anthropic API when the
Host has set its key, and the Host's subscription otherwise. A provider that needs
a key the Host has not set is refused, saying which setting to set.
"""

from collections.abc import Iterator, Mapping

from mm.llm.anthropic_api import AnthropicAPIProvider
from mm.llm.claude_agent_sdk import ClaudeAgentSDKProvider, SubscriptionError
from mm.llm.openai_compatible import VENDORS, OpenAICompatibleProvider
from mm.llm.protocol import ModelProvider

PROVIDERS_WITH_KEYS = ("anthropic", *VENDORS)
"""Providers reached with an API key; "claude" uses the "anthropic" one when it is set."""

NAMES = ("claude", *PROVIDERS_WITH_KEYS)


class Providers(Mapping[str, ModelProvider]):
    def __init__(self, api_keys: Mapping[str, str], concurrency: int = 5) -> None:
        """`api_keys` holds an API key by provider name: `anthropic`, `openai`, `openrouter`, ..."""
        self.api_keys, self.concurrency = api_keys, concurrency
        self._made: dict[str, ModelProvider] = {}

    def __getitem__(self, name: str) -> ModelProvider:
        if name not in NAMES:
            raise KeyError(name)
        if name not in self._made:
            self._made[name] = self._make(name)
        return self._made[name]

    def __iter__(self) -> Iterator[str]:
        return iter(NAMES)

    def __len__(self) -> int:
        return len(NAMES)

    def _make(self, name: str) -> ModelProvider:
        keyed = "anthropic" if name == "claude" else name
        key = self.api_keys.get(keyed)
        if name == "claude" and not key:
            try:
                return ClaudeAgentSDKProvider(concurrency=self.concurrency)
            except SubscriptionError as error:
                raise ValueError(f"claude: {error}") from error
        if not key:
            raise ValueError(f"{name} needs an API key: set MM_{keyed.upper()}_API_KEY")
        if keyed == "anthropic":
            return AnthropicAPIProvider(key, concurrency=self.concurrency)
        return OpenAICompatibleProvider.for_vendor(name, key, concurrency=self.concurrency)
