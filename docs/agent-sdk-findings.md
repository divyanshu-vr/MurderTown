# Claude Agent SDK: what we measured

Findings from running MurderTown's Agents through the Claude Agent SDK on a Claude Max subscription, with no API key. They decide how the `ClaudeAgentSDKProvider` is configured. Measured on 2026-10-28 with `claude-agent-sdk` 0.2.174 (bundled Claude Code 2.1.310), Windows 11, model `claude-haiku-5-5` at effort `low`.

To re-check them, run the opt-in live test: `MM_LIVE_TESTS=1 uv run pytest -s tests/test_live_claude.py` (four Haiku calls).

## Answers to the open questions

| Question | Finding |
|---|---|
| Does the subscription login work without an API key? | Yes. Each session reports `apiKeySource: "none"`; the bundled CLI's `auth status` reports `authMethod: claude.ai`. |
| Do tools stay off? | `tools=[]` leaves exactly one tool, `StructuredOutput`, which is how the SDK carries the structured answer. No MCP servers load with `strict_mcp_config`. |
| Does structured output work with every built-in tool disabled? | Yes. The answer arrives as a `StructuredOutput` tool call, so one answer takes **2 turns**; `max_turns` is 3. |
| Which JSON Schema dialect? | Flat draft-07-style schemas work. Answer schemas are generated from the decision models with `$defs` inlined and titles removed. |
| Is cost reported on the subscription? | Yes, as `total_cost_usd` at list prices: $0.0011 for an uncached first call, $0.0002 for a fully cached repeat. MurderTown prices every call itself from one table (`mm/llm/prices.py`), which reproduces Claude Code's figures exactly. |
| How long do cache writes last? | An hour on a subscription by default, five minutes as MurderTown sets it. `usage.cache_creation` splits writes into `ephemeral_1h_input_tokens` and `ephemeral_5m_input_tokens`; Claude Code writes one-hour entries on a subscription unless `CLAUDE_CODE_PROMPT_CACHE_TTL=5m`; one-hour writes cost twice the input price, five-minute ones a quarter above it. |
| What happens when a call fails? | The session yields a `ResultMessage` with `is_error` (its `result` holds the "API Error: ..." text), then the SDK raises `ResultError` because the CLI exits non-zero. The provider turns both, and any other SDK error, into an `error` reply, which aborts the game. |
| How long does a call take? | 0.6 to 1.6 s to start a session, 2.9 to 4.5 s for a whole call. |
| Does caching work? | Yes, automatically. A repeated identical prompt read 1,862 cached tokens. Whether it pays depends on the prompt's layout: see below. |

## A live game

One Day, 6 Residents, concurrency 5: 18 calls, all valid, no fallbacks, 49 seconds, $0.0149 equivalent cost.

| Tokens | Count |
|---|---|
| Output (including thinking) | 10,667 |
| Written to cache | 47,679 |
| Read from cache | 659 |

Haiku thinks about 95 tokens even for one sentence at effort `low`. Statements ran past the requested 60 words; the Open floor ticket truncates them.

**Caching did not pay off at first.** Every decision was a fresh session, and Claude Code caches the whole prompt, so a later call with the same briefing but a different task reused nothing, while writing its whole prompt to the cache at the one-hour price, twice the input price. Turning caching off would have made each call about 30% cheaper. The next section is how caching was made to pay instead.

## Making caching pay off

Measured on 2026-10-29 with the same versions, model `claude-haiku-5-5` at effort `low`. Equivalent prices per million tokens: input $0.10, cache read $0.01, five-minute cache write $0.125, one-hour cache write $0.20.

**What Claude Code caches.** A session's request begins with its tools, then the system prompt, then the messages. Claude Code marks two points for caching: the end of the system prompt, and the end of the last message. A later session reads back whatever begins exactly as an earlier one did, up to one of those points. Two of a Resident's decisions therefore shared nothing, for two reasons:
- the structured answer arrives through Claude Code's `StructuredOutput` tool, whose schema is the decision's answer format, so each kind of decision began differently;
- Claude Code's own per-session text (the account reminder, the environment and the date, about a thousand tokens) sits in the message, so it is written again by every session.

**What was tried**, on one Resident's first Statement and the ballot they cast next (the ballot's tokens):

| Layout | Read from cache | Written to cache |
|---|---|---|
| Before: the answer's schema per kind | 0 | 2,913 |
| One fixed answer schema | 1,279 | 1,510 |
| One fixed schema, the kind's schema in the task | 1,280 | 1,661 |
| The same, with the memory in the system prompt | 1,370 | 1,569 |
| A long-lived session per Resident (second turn) | 2,674 | 1,893 |
| Every answer format in the system prompt, five-minute writes | 3,449 | 1,431 |

A long-lived session reads its whole history back, but each turn still writes its new part at the one-hour price, so it costs as much as fresh sessions, and it carries every earlier task into the next. Writes are what make caching dear: at twice the input price, caching beats turning it off only when a call writes less than about 0.9 times what it reads.

**The choice.** Claude Code's `CLAUDE_CODE_PROMPT_CACHE_TTL=5m` makes cache writes last five minutes, at a quarter above the input price instead of twice it (unset, a subscription gets one-hour writes). And every session a Resident opens begins the same way:
- the system briefing lists the answer format of every decision that Resident may be asked (their role decides which), so it stays the same all game, and each task ends by naming the format to use;
- the answer tool's schema is the same for every decision: any object with at least one field. The agents check the answer against the decision's own format, as they always did; an answer nested one level down (under its format's name, or a field's) is taken out of it, since no answer is one field holding an object.

A Resident's first session writes the briefing (about 2,500 to 2,800 tokens); every later one reads it back and writes only the memory, the task and Claude Code's own text, which grow through a Day as the Day's transcript does.

**Live one-Day games**, 6 Residents, seed 3. Answers differ between runs, so the games differ in length:

| Game | Calls | Read from cache | Written to cache | Equivalent cost | Per call |
|---|---|---|---|---|---|
| Before #21: caching on, one-hour writes | 70 | 79,519 | 172,023 | $0.0506 | $0.000723 |
| Before #21, caching off | 101 | 0 | 0 | $0.0621 | $0.000615 |
| This layout, caching off | 78 | 0 | 0 | $0.0565 | $0.000724 |
| This layout, caching on | 75 | 196,918 | 178,497 | $0.0412 | $0.000549 |
| The same, again | 103 | 273,438 | 229,512 | $0.0546 | $0.000530 |

A game now reads more tokens from the cache than it writes (1.10 and 1.19 times as many in the two games), and costs less than the same game with caching off: 24 to 27% less per call than this layout with caching off, 11 to 14% less than the old layout with caching off, and 24 to 27% less than before #21 (counting the prompt alone, against the last two: 18% and 39%). Each setup was played once (this one with caching on, twice), so these are single measurements, not averages. The live game CI replays, re-recorded with this layout (6 Residents, 2 Days, 182 calls), read 525,206 tokens from the cache and wrote 442,341, at $0.000575 per call against $0.000781 for its recording before #21.

**Answers that break their format** rose from none to about one call in twenty in the first games: mostly answers nested one level down, which are now taken out, and empty answers, which Claude Code now refuses within the same session. The re-recorded game had two in 182. Claude Code no longer checks an answer's fields against its decision's format, so an answer missing a field is asked again in a new session, where Claude Code used to ask within the same one.

**The memory is not cached.** Claude Code marks only the end of the system prompt and of the last message, so the memory could be reused only from inside the system prompt. It changes at every Reflection, twice a Day, and the whole briefing would then be written again each time; on Day 1 the measured gain was 90 tokens a call. So the memory travels with the task, as before.

**Isolation still holds.** Every decision is still a fresh session with no saved history (`--no-session-persistence`). The cache adds nothing to what a model sees: it only matches a prompt that begins exactly as an earlier one did, and a Resident's briefing is theirs alone, listing only their own role's answer formats.

**Every provider gets the longer briefing.** The answer formats add about 1,000 tokens to it. The Anthropic API marks the briefing for caching, and OpenAI-compatible servers that cache a prompt's beginning reuse it too; one that caches nothing pays about 18% more per call (this layout with caching off, against the old one). A server that refuses the answer schema option sees the schema twice: in the briefing, and in the prompt.

## What Claude Code adds to every session

Even with a custom system prompt, about 1,000 tokens of scaffolding reach the model:

- a line about batching tool calls, appended to the system prompt;
- **a reminder containing the Host's account email**;
- an environment block: the working directory, operating system and platform;
- the current date.

No skill descriptions reach the model, although the session lists Claude Code's built-in skills. There is no switch for the email reminder that does not also change how Claude Code connects to the API, so two guards contain it:

- the system briefing tells every Agent to talk only about the town and never mention email addresses, computers or files;
- every answer is scrubbed before it can become an event or a stored model call (raw text, parsed answer and any problem quoting it): email addresses and file paths become `[hidden]`. Tests cover both.

## Settings that matter

- `CLAUDE_CODE_PROMPT_CACHE_TTL=5m`, and one answer schema for every decision (any object with at least one field): see Making caching pay off.
- `verbatim_prompts=True`: a prompt is delivered exactly as written. Without it, an `@path` in another Resident's Statement could make Claude Code read a local file.
- `--no-session-persistence` (passed through `extra_args`): games leave no transcripts in the Host's Claude Code history.
- The prompt travels over stdin as stream-JSON, never on the command line. The system prompt and schema do go on the command line, which is fine at a few kilobytes against Windows' 32 KB limit.
- Never use bare mode: it skips the subscription login.
- The provider refuses to start if `ANTHROPIC_API_KEY` or `ANTHROPIC_AUTH_TOKEN` is set, and stops if a session reports an API credential, an extra tool or an MCP server.
