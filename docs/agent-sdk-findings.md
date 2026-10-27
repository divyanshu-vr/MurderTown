# Claude Agent SDK: what we measured

Findings from running MurderTown's Agents through the Claude Agent SDK on a Claude Max subscription, with no API key. They decide how the `ClaudeAgentSDKProvider` is configured. Measured on 2026-10-28 with `claude-agent-sdk` 0.2.174 (bundled Claude Code 2.1.310), Windows 11, model `claude-haiku-5-5` at effort `low`.

To re-check them, run the opt-in live test: `MM_LIVE_TESTS=1 uv run pytest -s tests/test_live_claude.py` (two Haiku calls).

## Answers to the open questions

| Question | Finding |
|---|---|
| Does the subscription login work without an API key? | Yes. Each session reports `apiKeySource: "none"`; the bundled CLI's `auth status` reports `authMethod: claude.ai`. |
| Do tools stay off? | `tools=[]` leaves exactly one tool, `StructuredOutput`, which is how the SDK carries the structured answer. No MCP servers load with `strict_mcp_config`. |
| Does structured output work with every built-in tool disabled? | Yes. The answer arrives as a `StructuredOutput` tool call, so one answer takes **2 turns**; `max_turns` is 3. |
| Which JSON Schema dialect? | Flat draft-07-style schemas work. Answer schemas are generated from the decision models with `$defs` inlined and titles removed. |
| Is cost reported on the subscription? | Yes, as `total_cost_usd` at list prices: $0.0011 for an uncached first call, $0.0002 for a fully cached repeat. |
| How long does a call take? | 0.6 to 1.6 s to start a session, 2.9 to 4.5 s for a whole call. |
| Does caching work? | Yes, automatically, with a one-hour lifetime. A repeated identical prompt read 1,862 cached tokens. |

## A live game

One Day, 6 Residents, concurrency 5: 18 calls, all valid, no fallbacks, 49 seconds, $0.0149 equivalent cost.

| Tokens | Count |
|---|---|
| Output (including thinking) | 10,667 |
| Written to cache | 47,679 |
| Read from cache | 659 |

Haiku thinks about 95 tokens even for one sentence at effort `low`. Statements ran past the requested 60 words; the Open floor ticket truncates them.

**Caching rarely pays off here.** Every decision is a fresh session and Claude Code caches the whole prompt, so a later call with the same system briefing but a different task does not reuse it. Each call writes its whole prompt to the cache at the higher one-hour write price. Turning caching off (Claude Code's `DISABLE_PROMPT_CACHING`) would make a call about 30% cheaper; a long-lived session per Agent would reuse the briefing but carry history between decisions. This is left to the cost ticket.

## What Claude Code adds to every session

Even with a custom system prompt, about 1,000 tokens of scaffolding reach the model:

- a line about batching tool calls, appended to the system prompt;
- **a reminder containing the Host's account email**;
- an environment block: the working directory, operating system and platform;
- the current date.

No skill descriptions reach the model, although the session lists Claude Code's built-in skills. There is no switch for the email reminder that does not also change how Claude Code connects to the API, so two guards contain it:

- the system briefing tells every Agent to talk only about the town and never mention email addresses, computers or files;
- every answer is scrubbed before it can become an event: email addresses and file paths become `[hidden]`. A test covers it.

## Settings that matter

- `verbatim_prompts=True`: a prompt is delivered exactly as written. Without it, an `@path` in another Resident's Statement could make Claude Code read a local file.
- `--no-session-persistence` (passed through `extra_args`): games leave no transcripts in the Host's Claude Code history.
- The prompt travels over stdin as stream-JSON, never on the command line. The system prompt and schema do go on the command line, which is fine at a few kilobytes against Windows' 32 KB limit.
- Never use bare mode: it skips the subscription login.
- The provider refuses to start if `ANTHROPIC_API_KEY` or `ANTHROPIC_AUTH_TOKEN` is set, and stops if a session reports an API credential, an extra tool or an MCP server.
