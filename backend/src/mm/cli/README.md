# mm.cli: the `mm` command

Owns the terminal entry points. Run `uv run mm --help` for the commands and options.

**May import:** every layer.

**Entry points**
- `__init__.py`: the commands. `play` runs a game with scripted bots or Agents (`--provider claude`, or a whole `--lineup`), printing the transcript as it happens and saving events and model calls as NDJSON with `--out`, and `--replay` plays a saved game again from its recorded calls (see `docs/providers.md`); `serve` runs the API and prints the Host's link, which hands the browser the Host token (`MM_HOST_TOKEN`, or one kept in `runs/host-token`, made the first time); Ctrl+C, or SIGTERM on Linux, halts its games before their next decision, and they resume when it starts again; a second Ctrl+C stops at once, and games still resume, repeating only calls that were not recorded. `new-game` starts a game on a running API as the Host (`--host-token`, or the token `serve` uses), leaving the seed for the server to draw unless `--seed` is given; `export` writes a finished game's whole log from the server's database to a game file (NDJSON, the format `play --out` writes), which the console replays with no server, and its model calls beside it, so `play --replay` can play it again; `schema` exports the protocol; `minds` writes the server's mind of each Resident after each reflection in the recorded fixture, which the console's tests check its own fold against.
- `recording.py`: NDJSON files written as records happen, and the tally of model calls printed at the end.
- `transcript.py`: `describe(event)`, one readable line per event.

**Why it is shaped this way:** a headless game with a readable transcript is the fastest way to see a rule change working, without a browser.
