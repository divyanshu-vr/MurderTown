"""The `mm` command line: play games headlessly and inspect them."""

import asyncio
import json
import urllib.request
from pathlib import Path
from typing import Annotated

import typer
import uvicorn

from mm.agents import scripted_bots
from mm.api.protocol import protocol_schema
from mm.cli.transcript import describe
from mm.engine import GameConfig
from mm.engine.events import Event
from mm.orchestrator import play_game

app = typer.Typer(help="MurderTown: a town where every Resident is played by an Agent.")


@app.callback()
def main() -> None:
    """Keep `mm` a group of commands even while it has only a few."""


def write_events(path: Path, events: list[Event]) -> None:
    """Save a game as newline-delimited JSON, one event per line."""
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = (event.model_dump_json() for event in events)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


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
    out: Annotated[Path | None, typer.Option(help="Save the event log as NDJSON.")] = None,
    quiet: Annotated[bool, typer.Option(help="Do not print the transcript.")] = False,
) -> None:
    """Play one game with scripted bots and print its transcript."""
    config = GameConfig(
        residents=residents,
        murderers=murderers,
        seed=seed,
        max_days=max_days,
        doctor=doctor,
        detective=detective,
        sheriff=sheriff,
    )
    result = asyncio.run(play_game(config, scripted_bots(seed)))
    if not quiet:
        for event in result.events:
            typer.echo(describe(event))
    if out:
        write_events(out, result.events)
        typer.echo(f"Saved {len(result.events)} events to {out}")


@app.command()
def serve(host: str = "127.0.0.1", port: int = 8000, reload: bool = False) -> None:
    """Run the API server. Settings come from MM_* environment variables or .env."""
    uvicorn.run("mm.api:create_app", factory=True, host=host, port=port, reload=reload)


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
def schema(out: Path = Path("../protocol/murdertown.schema.json")) -> None:
    """Export the backend-frontend protocol as JSON Schema."""
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(protocol_schema(), indent=2) + "\n", encoding="utf-8")
    typer.echo(f"Wrote {out}")
