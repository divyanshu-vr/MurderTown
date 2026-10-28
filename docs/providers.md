# Who plays the Residents: providers, lineups and cassettes

## Lineups

A game's configuration includes its **lineup**: who plays each Resident. Each entry names a provider, a model and an effort; the provider `scripted` means a scripted bot. A seat's own entry wins, then its side's (`murderers` or `town`), then `everyone`'s. The narrator follows `everyone`. With no lineup, everyone is scripted.

```json
{
  "everyone": {"provider": "claude", "model": "claude-haiku-5-5", "effort": "low"},
  "murderers": {"provider": "claude", "model": "claude-sonnet-5-5", "effort": "medium"},
  "seats": {"3": {"provider": "scripted"}}
}
```

- `mm play --provider claude --model claude-haiku-5-5 --effort low` puts the same Agent in every seat; `mm play --lineup lineup.json` takes a whole lineup.
- `POST /games` takes it as the config's `lineup`. A lineup naming a provider the server cannot reach, or a model with no price, is refused with a 422 before anything is stored.

## Providers

| Name | What it is | Needs |
|---|---|---|
| `claude` | Claude: on the Anthropic API when `MM_ANTHROPIC_API_KEY` is set, otherwise on your Claude subscription through the Claude Agent SDK | a key, or `claude auth login` |
| `anthropic` | Claude on the Anthropic API | `MM_ANTHROPIC_API_KEY` |
| `openai` | OpenAI | `MM_OPENAI_API_KEY` |
| `openrouter` | OpenRouter (routes only to providers that honour every option) | `MM_OPENROUTER_API_KEY` |
| `gemini` | Google Gemini, through its OpenAI-compatible endpoint | `MM_GEMINI_API_KEY` |
| `xai` | xAI | `MM_XAI_API_KEY` |

Set keys in `backend/.env` (never `ANTHROPIC_API_KEY`: the subscription provider refuses to start while it is set, so subscription games can never be billed to an API key). Every provider sends the same prompts. The Anthropic API marks the briefing and the Resident's memory for caching. The OpenAI-compatible providers ask for the answer in its JSON schema at the Resident's effort (`reasoning_effort`); a server that refuses either option for a model is asked again without it, and the schema then goes into the prompt.

**Prices.** Every call's equivalent cost comes from one table, `backend/src/mm/llm/prices.py`, which holds Claude's list prices. A model that is not in it cannot play: add its price per million tokens (input, output, cache read) first.

## Cassettes

A cassette is a recorded game's model calls, played back with no model and no network. `mm play --out game.ndjson` saves the game's events and, beside them, every model call in `game.calls.ndjson`, scrubbed of details from outside the game. `mm play --replay game.ndjson` plays the same game again from those records.

CI replays `fixtures/live-game.ndjson`, a short live Claude game, and checks that the replay makes exactly the recorded log (`tests/test_providers.py`).

Each recorded call answers only the very same request: the same model, effort, briefing, prompt and answer schema. So **any change to the prompts** (templates, personas, rendering, schemas) makes the replay miss, and CI fails saying to re-record. Re-record on the subscription (about 60 Haiku calls, a couple of minutes):

```
cd backend
uv run mm play --provider claude --residents 6 --murderers 1 --max-days 2 --seed 3 --quiet --out ../fixtures/live-game.ndjson
```

A recording whose game was aborted cannot be used: run it again.
