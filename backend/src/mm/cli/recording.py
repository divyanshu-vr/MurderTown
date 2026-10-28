"""Recording a headless game: event and model-call logs on disk, and a running tally of calls."""

import json
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path

from pydantic import BaseModel

from mm.agents import Cost, ModelCall
from mm.engine.events import Event
from mm.review import review_of


def calls_beside(events: Path) -> Path:
    """Where `mm play --out` keeps the model calls of the game it saved at `events`."""
    return events.with_suffix(".calls.ndjson")


def review_beside(events: Path) -> Path:
    """Where the review of the game saved at `events` is kept, for replays to show."""
    return events.with_suffix(".review.json")


def write_json(path: Path, data: object) -> None:
    """Write `data` as indented JSON, ending with a newline, whatever the platform."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8", newline="\n")


def write_review_beside(events_file: Path, events: Sequence[Event]) -> None:
    write_json(review_beside(events_file), review_of(events).model_dump(mode="json"))


def ndjson_line(record: BaseModel) -> str:
    return record.model_dump_json() + "\n"


def write_ndjson(path: Path, records: Sequence[BaseModel]) -> None:
    """Write every record at once, one JSON line each."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(map(ndjson_line, records)), encoding="utf-8", newline="\n")


def read_ndjson[R: BaseModel](path: Path, record: type[R]) -> list[R]:
    """Every record in an NDJSON file, skipping blank lines."""
    lines = path.read_text(encoding="utf-8").splitlines()
    return [record.model_validate_json(line) for line in lines if line.strip()]


class NdjsonFile:
    """Appends one JSON line per record as it happens, so a crash loses nothing already written."""

    def __init__(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("", encoding="utf-8")
        self.path = path
        self.count = 0

    async def __call__(self, record: BaseModel) -> None:
        with self.path.open("a", encoding="utf-8", newline="\n") as file:
            file.write(ndjson_line(record))
        self.count += 1


@dataclass
class CallTally:
    """Totals across every model call of a game, for the summary printed at the end."""

    outcomes: Counter[str] = field(default_factory=Counter)
    cost: Cost = field(default_factory=Cost)

    async def __call__(self, call: ModelCall) -> None:
        self.outcomes[call.outcome] += 1
        self.cost += Cost.of([call])

    def summary(self) -> str:
        cost = self.cost
        outcomes = ", ".join(
            f"{count} {outcome}" for outcome, count in sorted(self.outcomes.items())
        )
        return (
            f"{cost.calls} model calls ({outcomes}). Tokens: {cost.input_tokens} in, "
            f"{cost.output_tokens} out, {cost.cache_read_tokens} read from cache, "
            f"{cost.cache_write_tokens} written to cache. "
            f"Equivalent API cost: ${cost.cost_usd:.4f}."
        )
