"""The `mm` command line: play games headlessly and inspect them."""

import asyncio
import json
import logging
import urllib.request
from enum import StrEnum
from pathlib import Path
from typing import Annotated

import typer
import uvicorn

from mm.agents import AgentSettings, BrainFactory, ModelCall, llm_agents, scripted_bots
from mm.agents.memory import mind_of
from mm.api.protocol import protocol_schema
from mm.cli.recording import CallTally, NdjsonFile
from mm.cli.transcript import describe
from mm.engine import GameConfig
from mm.engine.events import DecisionFellBack, Event, ReflectionWritten
from mm.llm import Effort
from mm.llm.claude_agent_sdk import ClaudeAgentSDKProvider, SubscriptionError
from mm.observability import observed
from mm.orchestrator import EventObserver, play_game

app = typer.Typer(help="MurderTown: a town where every Resident is played by an Agent.")


class Brains(StrEnum):
    SCRIPTED = "scripted"
    CLAUDE = "claude"


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
    brains: Annotated[Brains, typer.Option(help="Who plays the Residents.")] = Brains.SCRIPTED,
    model: str = AgentSettings.model,
    effort: Effort = AgentSettings.effort,
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

    With --brains claude, every Resident is an Agent on your Claude subscription.
    With --out game.ndjson, model calls are also saved to game.calls.ndjson.
    """
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
    )
    tally = CallTally()
    observers: list[EventObserver] = []
    if not quiet:
        observers.append(_print_event)
    events_file = NdjsonFile(out) if out else None
    if events_file:
        observers.append(events_file)

    try:
        brain_for = _brains(
            brains,
            config=config,
            model=model,
            effort=effort,
            concurrency=concurrency,
            tally=tally,
            out=out,
        )
    except SubscriptionError as error:
        typer.echo(f"Cannot start a live game: {error}", err=True)
        raise typer.Exit(code=1) from error

    with observed(logging.getLevelNamesMapping()[log_level.upper()]):
        result = asyncio.run(play_game(config, brain_for, observers))
    fallbacks = sum(isinstance(event.payload, DecisionFellBack) for event in result.events)
    if brains is Brains.CLAUDE:
        typer.echo(f"\n{tally.summary()} Fallbacks: {fallbacks}.")
    if events_file:
        typer.echo(f"Saved {events_file.count} events to {out}")


def _brains(
    brains: Brains,
    *,
    config: GameConfig,
    model: str,
    effort: Effort,
    concurrency: int,
    tally: CallTally,
    out: Path | None,
) -> BrainFactory:
    if brains is Brains.SCRIPTED:
        return scripted_bots(config.seed)
    provider = ClaudeAgentSDKProvider(concurrency=concurrency)
    calls_file = NdjsonFile(out.with_suffix(".calls.ndjson")) if out else None

    async def record(call: ModelCall) -> None:
        await tally(call)
        if calls_file:
            await calls_file(call)

    return llm_agents(provider, AgentSettings(model=model, effort=effort), record, config.seed)


async def _print_event(event: Event) -> None:
    if (line := describe(event)) is not None:
        typer.echo(line)


@app.command()
def serve(host: str = "127.0.0.1", port: int = 8000, reload: bool = False) -> None:
    """Run the API server. Settings come from MM_* environment variables or .env.

    Logs are JSON lines on stderr; traces go wherever the MM_LANGFUSE_* or
    MM_OTLP_ENDPOINT settings say (see backend/.env.example).
    """
    uvicorn.run("mm.api.app:observed_app", factory=True, host=host, port=port, reload=reload)


@app.command()
def new_game(
    *,
    api: str = "http://127.0.0.1:8000",
    web: str = "http://localhost:5173",
    residents: int = 12,
    murderers: int = 2,
    seed: int = 7,
    max_days: int = 10,
) -> None:
    """Start a scripted game on a running server and print where to watch it."""
    config = {"residents": residents, "murderers": murderers, "seed": seed, "max_days": max_days}
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
    log = [Event.model_validate_json(line) for line in events.read_text("utf-8").splitlines()]
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
