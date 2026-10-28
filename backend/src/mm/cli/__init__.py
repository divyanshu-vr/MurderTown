"""The `mm` command line: play games headlessly and inspect them."""

import asyncio
import json
import logging
import os
import secrets
import urllib.request
from collections.abc import Mapping
from pathlib import Path
from typing import Annotated

import typer
import uvicorn

from mm.agents import ModelCall
from mm.agents.calls import unrecorded
from mm.agents.cassette import Cassette
from mm.agents.lineup import lineup_brains
from mm.agents.memory import mind_of
from mm.api.protocol import protocol_schema
from mm.api.routes import HOST_TOKEN_HEADER
from mm.api.settings import Settings
from mm.cli.evaluation import MatrixChangedError, play_batch
from mm.cli.matrix import Cell, Matrix
from mm.cli.recording import (
    CallTally,
    GameRecording,
    calls_beside,
    read_ndjson,
    write_json,
    write_ndjson,
    write_review_beside,
)
from mm.cli.report import write_report
from mm.cli.transcript import SIDES, describe
from mm.engine import SCRIPTED, GameConfig, Lineup, PlayedBy
from mm.engine.events import DecisionFellBack, Event, GameConfigured, ReflectionWritten
from mm.llm import Effort, ModelProvider
from mm.llm.providers import NAMES
from mm.observability import observed
from mm.orchestrator import EventObserver, GameResult, play_game
from mm.persistence import UNFINISHED, GameStore, open_database

app = typer.Typer(help="MurderTown: a town where every Resident is played by an Agent.")

CONNECTION_GRACE_SECONDS = 5
"""How long the server waits for open connections to close before it halts its games."""


AGENT = PlayedBy()
"""The Agent `--provider claude` puts in every seat unless told otherwise."""

Provider = Annotated[
    str, typer.Option(help=f"Who plays every Resident: scripted, or one of {', '.join(NAMES)}.")
]

LogLevel = Annotated[
    str, typer.Option(help="JSON log lines on stderr from this level up, e.g. info.")
]

LIVE_GAME = Path("../fixtures/live-game.ndjson")
"""The live game CI replays from its recorded model calls."""

HOST_TOKEN_FILE = Path("runs/host-token")
"""Where the Host token is kept when MM_HOST_TOKEN is not set, so it stays the same between runs."""

EVALUATIONS = Path("runs/evaluations")
"""Where `mm evaluate` keeps each matrix's run, in a folder named after the matrix."""

STOPPED = {
    "complete": "Every game is played.",
    "capped": "Stopped at this batch's cap of games: run the same command again to go on.",
    "aborted": "Stopped because a game aborted ({reason}): run the same command again to play "
    "it once more.",
}
"""What `mm evaluate` says when a batch stops, by why it stopped."""

WEB = "http://localhost:5173"
"""Where the frontend's dev server runs."""


def _host_token() -> str:
    """The Host token: MM_HOST_TOKEN if it is set (in the environment or .env), or else the one
    kept in runs/host-token, made the first time it is needed."""
    if (token := Settings().host_token) is not None:
        return token.get_secret_value()
    if not HOST_TOKEN_FILE.exists():
        HOST_TOKEN_FILE.parent.mkdir(parents=True, exist_ok=True)
        HOST_TOKEN_FILE.write_text(secrets.token_urlsafe(24), encoding="utf-8")
    return HOST_TOKEN_FILE.read_text(encoding="utf-8").strip()


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
    log_level: LogLevel = "warning",
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
    recording = GameRecording(out) if out else None
    tally = recording.tally if recording else CallTally()
    observers: list[EventObserver] = [] if quiet else [_print_event]
    if recording:
        observers.append(recording.events)
    try:
        brains = lineup_brains(config, providers, recording.record if recording else tally)
    except ValueError as error:  # a provider not available, or a model with no price
        typer.echo(f"Cannot start the game: {error}", err=True)
        raise typer.Exit(code=1) from error

    with observed(_level(log_level)):
        result = asyncio.run(play_game(config, brains, observers=observers))
    if tally.cost.calls:
        fallbacks = sum(isinstance(event.payload, DecisionFellBack) for event in result.events)
        typer.echo(f"\n{tally.summary()} Fallbacks: {fallbacks}.")
    if recording:
        recording.finish(result.events)
        typer.echo(f"Saved {recording.events.count} events and their review to {out}")
    if result.state.aborted:
        raise typer.Exit(code=1)  # the transcript says why


def _recorded(events: Path) -> tuple[GameConfig, Mapping[str, ModelProvider]]:
    """A saved game's configuration, and its recorded model calls standing in for every model."""
    configured = read_ndjson(events, Event)[0].payload
    if not isinstance(configured, GameConfigured):
        raise typer.BadParameter(f"{events} does not start with a game")
    calls_file = calls_beside(events)
    calls = read_ndjson(calls_file, ModelCall) if calls_file.exists() else []
    return configured.config, Cassette.serving(calls)


async def _print_event(event: Event) -> None:
    if (line := describe(event)) is not None:
        typer.echo(line)


@app.command()
def serve(host: str = "127.0.0.1", port: int = 8000, reload: bool = False, web: str = WEB) -> None:
    """Run the API server. Settings come from MM_* environment variables or .env.

    Only the Host may start and control games: open the link it prints, which hands your
    browser the Host token (MM_HOST_TOKEN, or one kept in runs/host-token).

    Logs are JSON lines on stderr; traces go wherever the MM_LANGFUSE_* or
    MM_OTLP_ENDPOINT settings say (see backend/.env.example). Stop it with Ctrl+C (or
    SIGTERM on Linux): games stop before their next decision and resume at the next start.
    A second Ctrl+C stops at once; games still resume, repeating only unrecorded calls.
    """
    os.environ["MM_HOST_TOKEN"] = token = _host_token()  # read by the server, reloads included
    typer.echo(f"Host: open {web}/#host-token={token} to start and control games.")
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
def evaluate(
    matrix_file: Annotated[
        Path, typer.Argument(metavar="MATRIX", help="The matrix to play: a TOML file.")
    ],
    out: Annotated[
        Path | None,
        typer.Option(help="The run's folder: runs/evaluations/<the matrix's name> if left out."),
    ] = None,
    concurrency: Annotated[int, typer.Option(help="Agents thinking at once.")] = 5,
    log_level: LogLevel = "warning",
) -> None:
    """Play a matrix of game configurations headlessly, then report what came of every game.

    Games are played one at a time, at most the matrix's games_per_batch of them, waiting
    pause_seconds between them. Run the same command again to go on where it stopped, so an
    evaluation on your subscription can be played in batches as its quota allows. A game that
    aborts, as every game does once the quota runs out, stops the batch and is played again next
    time. The report (report.md in the run's folder) is written again after every batch. A
    matrix with contenders is an arena, and its report adds a leaderboard (docs/evaluation.md).
    """
    try:
        matrix = Matrix.read(matrix_file)
        cells = matrix.cells()
    except (OSError, ValueError) as error:  # unreadable, not TOML, or games the rules forbid
        raise typer.BadParameter(f"{matrix_file} cannot be played: {error}") from error
    providers = Settings().providers(concurrency)
    try:
        for cell in cells:  # a provider not available, or a model with no price
            lineup_brains(cell.config(matrix.first_seed), providers, unrecorded)
    except ValueError as error:
        typer.echo(f"Cannot evaluate: {error}", err=True)
        raise typer.Exit(code=1) from error
    folder = out or EVALUATIONS / matrix.name
    try:
        with observed(_level(log_level)):
            batch = asyncio.run(play_batch(matrix, folder, providers, on_game=_print_game))
    except MatrixChangedError as error:
        typer.echo(f"Cannot evaluate: {error}", err=True)
        raise typer.Exit(code=1) from error
    report = write_report(folder)
    typer.echo(f"{STOPPED[batch.stopped].format(reason=batch.reason)} Report: {report}")
    if batch.stopped == "aborted":
        raise typer.Exit(code=1)


def _level(name: str) -> int:
    return logging.getLevelNamesMapping()[name.upper()]


def _print_game(cell: Cell, seed: int, result: GameResult) -> None:
    state = result.state
    outcome = f"the {SIDES[state.winner]} won on Day {state.day}" if state.winner else "aborted"
    typer.echo(f"Cell {cell.index} ({cell.name}), seed {seed}: {outcome}")


@app.command()
def export(
    game_id: str,
    out: Annotated[
        Path | None, typer.Option(help="Where to write it: <game id>.ndjson if left out.")
    ] = None,
) -> None:
    """Write a finished game's whole log to a game file, as the server stored it, with its
    review beside it, and its model calls, as `play --out` does, so `play --replay` can play it
    again.

    The console replays a game file with no server: serve it with the frontend and open
    /replay?file=<its address>. The file holds every event, the seed and roles included.
    """
    out = out or Path(f"{game_id}.ndjson")
    events, calls = asyncio.run(_finished_game(game_id))
    write_ndjson(out, events)
    write_review_beside(out, events)
    if calls:
        write_ndjson(calls_beside(out), calls)
    typer.echo(f"Saved {len(events)} events, their review and {len(calls)} model calls to {out}")


async def _finished_game(game_id: str) -> tuple[list[Event], list[ModelCall]]:
    engine = open_database(Settings().database_url)
    try:
        store = GameStore(engine)
        game = await store.game(game_id)
        if game is None:
            raise typer.BadParameter(f"There is no game {game_id}")
        if game.status in UNFINISHED:
            raise typer.BadParameter(f"Game {game_id} has not ended: it is {game.status}")
        return await store.events(game_id), await store.calls(game_id)
    finally:
        await engine.dispose()


@app.command()
def new_game(
    *,
    api: str = "http://127.0.0.1:8000",
    web: str = WEB,
    residents: int = 12,
    murderers: int = 2,
    seed: Annotated[
        int | None, typer.Option(help="Leave it out for a random one: a known seed tells roles.")
    ] = None,
    max_days: int = 10,
    provider: Provider = SCRIPTED.provider,
    model: str = AGENT.model,
    effort: Effort = AGENT.effort,
    host_token: Annotated[
        str | None, typer.Option(help="The server's Host token, if not MM_HOST_TOKEN's.")
    ] = None,
) -> None:
    """Start a game on a running server, as the Host, and print where to watch it."""
    chosen = {"seed": seed} if seed is not None else {}
    config = GameConfig(
        residents=residents,
        murderers=murderers,
        max_days=max_days,
        lineup=_everyone(provider, model, effort),
        **chosen,
    ).model_dump(mode="json", exclude_unset=True)
    request = urllib.request.Request(
        f"{api}/games",
        data=json.dumps(config).encode(),
        headers={
            "Content-Type": "application/json",
            HOST_TOKEN_HEADER: host_token or _host_token(),
        },
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
    write_json(out, minds)
    typer.echo(f"Saved {len(minds)} minds to {out}")


@app.command()
def schema(out: Path = Path("../protocol/murdertown.schema.json")) -> None:
    """Export the backend-frontend protocol as JSON Schema."""
    write_json(out, protocol_schema())
    typer.echo(f"Wrote {out}")
