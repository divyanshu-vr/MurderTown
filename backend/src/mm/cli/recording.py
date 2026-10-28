"""Recording a headless game: event and model-call logs on disk, and a running tally of calls."""

from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

from pydantic import BaseModel

from mm.agents import Cost, ModelCall


def calls_beside(events: Path) -> Path:
    """Where `mm play --out` keeps the model calls of the game it saved at `events`."""
    return events.with_suffix(".calls.ndjson")


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
            file.write(record.model_dump_json() + "\n")
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
