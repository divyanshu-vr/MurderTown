"""The `mm` command line: play games headlessly and inspect them."""

import asyncio
import json
import logging
import urllib.request
from collections.abc import Mapping
from pathlib import Path
from typing import Annotated

import typer
import uvicorn

from mm.agents import ModelCall
from mm.agents.cassette import Cassette
from mm.agents.lineup import lineup_brains
from mm.agents.memory import mind_of
from mm.api.protocol import protocol_schema
from mm.api.settings import Settings
from mm.cli.recording import CallTally, NdjsonFile, calls_beside, read_ndjson
from mm.cli.transcript import describe
from mm.engine import SCRIPTED, GameConfig, Lineup, PlayedBy
from mm.engine.events import DecisionFellBack, Event, GameStarted, ReflectionWritten
from mm.llm import Effort, ModelProvider
from mm.llm.providers import NAMES
from mm.observability import observed
from mm.orchestrator import EventObserver, play_game

app = typer.Typer(help="MurderTown: a town where every Resident is played by an Agent.")

CONNECTION_GRACE_SECONDS = 5
"""How long the server waits for open connections to close before it halts its games."""


AGENT = PlayedBy()
"""The Agent `--provider claude` puts in every seat unless told otherwise."""

Provider = Annotated[
    str, typer.Option(help=f"Who plays every Resident: scripted, or one of {', '.join(NAMES)}.")
]

LIVE_GAME = Path("../fixtures/live-game.ndjson")
"""The live game CI replays from its recorded model calls."""


def _everyone(provider: str, model: str, effort: Effort) -> Lineup:
    """A lineup with the same player in every seat."""
    return Lineup(everyone=PlayedBy(provider=provider, model=model, effort=effort))


@app.callback()
def main() -> None:
    """Keep `mm` a group of commands even while it has only a few."""


@app.command()
def play(
    *,
    residents: int = 12,
    murderers: int = 2,
    seed: int = 7,
    max_days: int = 10,
    doctor: bool = True,
    detective: bool = True,
    sheriff: bool = True,
    provider: Provider = SCRIPTED.provider,
    model: str = AGENT.model,
    effort: Effort = AGENT.effort,
    lineup: Annotated[
        Path | None, typer.Option(help="A JSON lineup of who plays each side or seat.")
    ] = None,
    replay: Annotated[
        Path | None,
        typer.Option(help="Replay a game saved with --out from its recorded model calls."),
    ] = None,
    concurrency: Annotated[int, typer.Option(help="Agents thinking at once.")] = 5,
    open_floor_statements: Annotated[
        int, typer.Option(help="Statements allowed on each Open floor; 0 skips it.")
    ] = GameConfig.model_fields["open_floor_statements"].default,
    open_floor_seconds: Annotated[
        int | None, typer.Option(help="Time limit on each Open floor; off by default here.")
    ] = None,
    out: Annotated[Path | None, typer.Option(help="Save the event log as NDJSON.")] = None,
    quiet: Annotated[bool, typer.Option(help="Do not print the transcript.")] = False,
    log_level: Annotated[
        str, typer.Option(help="JSON log lines on stderr from this level up, e.g. info.")
    ] = "warning",
) -> None:
    """Play one game and print its transcript as it happens.

    With --provider claude, every Resident is an Agent on your Claude subscription (or
    the Anthropic API, if MM_ANTHROPIC_API_KEY is set). --lineup gives sides or seats
    their own provider, model and effort. With --out game.ndjson, model calls are also
    saved to game.calls.ndjson, which --replay game.ndjson plays back with no model.
    """
    if replay:
        config, providers = _recorded(replay)
    else:
        config = GameConfig(
            residents=residents,
            murderers=murderers,
            seed=seed,
            max_days=max_days,
            doctor=doctor,
            detective=detective,
            sheriff=sheriff,
            open_floor_statements=open_floor_statements,
            open_floor_seconds=open_floor_seconds,
            lineup=Lineup.model_validate_json(lineup.read_text(encoding="utf-8"))
            if lineup
            else _everyone(provider, model, effort),
        )
        providers = Settings().providers(concurrency)
    tally = CallTally()
    calls_file: NdjsonFile | None = None  # made with the first call, so scripted games have none
    events_file = NdjsonFile(out) if out else None
    observers: list[EventObserver] = [] if quiet else [_print_event]
    if events_file:
        observers.append(events_file)

    async def record(call: ModelCall) -> None:
        nonlocal calls_file
        await tally(call)
        if out:
            calls_file = calls_file or NdjsonFile(calls_beside(out))
            await calls_file(call)

    try:
        brains = lineup_brains(config, providers, record)
    except ValueError as error:  # a provider not available, or a model with no price
        typer.echo(f"Cannot start the game: {error}", err=True)
        raise typer.Exit(code=1) from error

    with observed(logging.getLevelNamesMapping()[log_level.upper()]):
        result = asyncio.run(play_game(config, brains, observers=observers))
    if tally.cost.calls:
        fallbacks = sum(isinstance(event.payload, DecisionFellBack) for event in result.events)
        typer.echo(f"\n{tally.summary()} Fallbacks: {fallbacks}.")
    if events_file:
        typer.echo(f"Saved {events_file.count} events to {out}")
    if result.state.aborted:
        raise typer.Exit(code=1)  # the transcript says why


def _recorded(events: Path) -> tuple[GameConfig, Mapping[str, ModelProvider]]:
    """A saved game's configuration, and its recorded model calls standing in for every model."""
    started = read_ndjson(events, Event)[0].payload
    if not isinstance(started, GameStarted):
        raise typer.BadParameter(f"{events} does not start with a game")
    calls_file = calls_beside(events)
    calls = read_ndjson(calls_file, ModelCall) if calls_file.exists() else []
    return started.config, Cassette.serving(calls)


async def _print_event(event: Event) -> None:
    if (line := describe(event)) is not None:
        typer.echo(line)


@app.command()
def serve(host: str = "127.0.0.1", port: int = 8000, reload: bool = False) -> None:
    """Run the API server. Settings come from MM_* environment variables or .env.

    Logs are JSON lines on stderr; traces go wherever the MM_LANGFUSE_* or
    MM_OTLP_ENDPOINT settings say (see backend/.env.example). Stop it with Ctrl+C (or
    SIGTERM on Linux): games stop before their next decision and resume at the next start.
    A second Ctrl+C stops at once; games still resume, repeating only unrecorded calls.
    """
    uvicorn.run(
        "mm.api.app:observed_app",
        factory=True,
        host=host,
        port=port,
        reload=reload,
        timeout_graceful_shutdown=CONNECTION_GRACE_SECONDS,  # Spectators' sockets stay open
    )


@app.command()
def rerecord(out: Path = LIVE_GAME) -> None:
    """Record again, on your Claude subscription, the live game CI replays (about 180 Haiku calls).

    Needed after any change to the prompts: the old recording no longer answers them.
    """
    play(provider="claude", residents=6, murderers=1, max_days=2, seed=3, quiet=True, out=out)


@app.command()
def new_game(
    *,
    api: str = "http://127.0.0.1:8000",
    web: str = "http://localhost:5173",
    residents: int = 12,
    murderers: int = 2,
    seed: int = 7,
    max_days: int = 10,
    provider: Provider = SCRIPTED.provider,
    model: str = AGENT.model,
    effort: Effort = AGENT.effort,
) -> None:
    """Start a game on a running server and print where to watch it."""
    config = GameConfig(
        residents=residents,
        murderers=murderers,
        seed=seed,
        max_days=max_days,
        lineup=_everyone(provider, model, effort),
    ).model_dump(mode="json")
    request = urllib.request.Request(
        f"{api}/games",
        data=json.dumps(config).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request) as response:
        game_id = json.load(response)["id"]
    typer.echo(f"Game {game_id} started. Watch it at {web}/games/{game_id}")


@app.command()
def minds(
    events: Path = Path("../fixtures/scripted-game.ndjson"),
    out: Path = Path("../fixtures/scripted-game.minds.json"),
) -> None:
    """Write each Resident's mind right after each reflection they wrote, as the server builds it.

    The console folds minds itself, so replays need no backend. This file lets the
    console's tests check that its fold agrees with the server's at every change.
    """
    log = read_ndjson(events, Event)
    minds = []
    for event in log:
        if isinstance(event.payload, ReflectionWritten):
            mind = mind_of(log[: event.seq], event.payload.resident)
            assert mind is not None, "a Resident who reflects has a role"
            folded = mind.model_dump(mode="json", exclude={"perceived"})
            minds.append({"seq": event.seq, "mind": folded})
    out.write_text(json.dumps(minds, indent=1) + "\n", encoding="utf-8", newline="\n")
    typer.echo(f"Saved {len(minds)} minds to {out}")


@app.command()
def schema(out: Path = Path("../protocol/murdertown.schema.json")) -> None:
    """Export the backend-frontend protocol as JSON Schema."""
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(protocol_schema(), indent=2) + "\n", encoding="utf-8", newline="\n")
    typer.echo(f"Wrote {out}")
