# mm.cli: the `mm` command

Owns the terminal entry points. Run `uv run mm --help` for the commands and options.

**May import:** every layer.

**Entry points**
- `__init__.py`: the commands. `play` runs a scripted game and prints its transcript (and can save its event log as NDJSON); `serve` runs the API; `new-game` starts a game on a running API; `schema` exports the protocol.
- `transcript.py`: `describe(event)`, one readable line per event.

**Why it is shaped this way:** a headless game with a readable transcript is the fastest way to see a rule change working, without a browser.
