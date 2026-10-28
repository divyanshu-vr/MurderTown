# mm.llm: language-model providers

Owns talking to a language model. A provider takes a system prompt, a user prompt, an answer schema (which the agents check every answer against, so a provider that cannot enforce it without changing its prompt's beginning may leave it to them), a model and an effort level, and returns the structured answer with its raw text, token usage, latency and outcome (`ok`, `refusal`, `timeout` or `error`). A failed call is a reply (`ModelReply.failure`), not an exception; the pipeline treats a provider that raises anyway as an error too.

**May import:** `mm.engine` (a lineup's `Effort`).

**Entry points**
- `protocol.py`: the `ModelProvider` interface, `ModelRequest`, `ModelReply` and `Usage` (cache writes split into five-minute and one-hour ones, which are priced differently).
- `prices.py`: the one price table. `equivalent_cost(model, usage)` prices any call at the Claude API's list prices, whichever provider made it.
- `providers.py`: `Providers`, the providers a Host can use by name, each made when a game first asks for it; `"claude"` is the Anthropic API when its key is set, the subscription otherwise.
- `anthropic_api.py`: `AnthropicAPIProvider`, Claude on the Anthropic API, with the briefing and memory marked for caching.
- `openai_compatible.py`: `OpenAICompatibleProvider` for OpenAI, OpenRouter, Gemini and xAI, which drops an option a server refuses for a model and remembers it.
- `calling.py`: `CallLimits`, how every provider makes its calls: a few at a time, each given up after a time limit that covers any retries.
- `claude_agent_sdk.py`: `ClaudeAgentSDKProvider`, Claude through the Claude Agent SDK on the Host's subscription. Each call is an isolated Claude Code session with no tools, settings, MCP servers, memory or saved history, bounded by a concurrency limit and a per-call timeout that ends the subprocess. It refuses to start without the subscription login. Every session a Resident opens begins the same way (the briefing as its system prompt, and an answer tool that takes any object), so Claude Code reads it back from the cache; cache writes last five minutes, the cheaper kind.

**Why it is shaped this way:** providers only talk to a model. Reading the answer, retrying and falling back happen once in `mm.agents`, so every provider behaves the same to the rest of the game. What we measured about the SDK is in `docs/agent-sdk-findings.md`.
