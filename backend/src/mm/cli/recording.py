"""Recording a headless game: event and model-call logs on disk, and a running tally of calls."""

from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

from pydantic import BaseModel

from mm.agents import ModelCall


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
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_tokens: int = 0
    cache_write_tokens: int = 0
    cost_usd: float = 0.0

    async def __call__(self, call: ModelCall) -> None:
        self.outcomes[call.outcome] += 1
        self.input_tokens += call.input_tokens
        self.output_tokens += call.output_tokens
        self.cache_read_tokens += call.cache_read_tokens
        self.cache_write_tokens += call.cache_write_tokens
        self.cost_usd += call.cost_usd or 0.0

    def summary(self) -> str:
        calls = sum(self.outcomes.values())
        outcomes = ", ".join(
            f"{count} {outcome}" for outcome, count in sorted(self.outcomes.items())
        )
        return (
            f"{calls} model calls ({outcomes}). Tokens: {self.input_tokens} in, "
            f"{self.output_tokens} out, {self.cache_read_tokens} read from cache, "
            f"{self.cache_write_tokens} written to cache. "
            f"Equivalent API cost: ${self.cost_usd:.4f}."
        )
