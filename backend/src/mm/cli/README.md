# mm.cli: the `mm` command

Owns the terminal entry points. Run `uv run mm --help` for the commands and options.

**May import:** every layer.

**Entry points**
- `__init__.py`: the commands. `play` runs a game with scripted bots or, with `--brains claude`, LLM Agents on the Host's subscription, printing the transcript as it happens and saving events and model calls as NDJSON with `--out`; `serve` runs the API; `new-game` starts a game on a running API; `schema` exports the protocol.
- `recording.py`: NDJSON files written as records happen, and the tally of model calls printed at the end.
- `transcript.py`: `describe(event)`, one readable line per event.

**Why it is shaped this way:** a headless game with a readable transcript is the fastest way to see a rule change working, without a browser.
