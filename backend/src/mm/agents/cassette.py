"""Cassettes: a recorded game's model calls, played back with no model.

`mm play --out game.ndjson` keeps every model call of a game, scrubbed, in
`game.calls.ndjson`. A cassette answers a replay of that game from those records,
each record answering the very same request again: the same model, effort, briefing,
prompt and answer schema. So any change to a prompt makes the cassette miss, loudly,
and the game must be recorded again. Identical requests replay in the order they were
made.
"""

import hashlib
import json
from collections import defaultdict
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any

from mm.agents.answers import answer_schema
from mm.agents.calls import ModelCall
from mm.engine import Effort
from mm.llm import ModelProvider, ModelReply, ModelRequest


class CassetteMissError(Exception):
    """A replayed game asked something its cassette does not hold."""


def key(model: str, effort: Effort, system: str, prompt: str, schema: Mapping[str, Any]) -> str:
    """Everything a model was asked, hashed."""
    asked = [model, effort, system, prompt, schema]
    return hashlib.sha256(json.dumps(asked, sort_keys=True).encode()).hexdigest()


class Cassette:
    """A provider that answers from a recorded game's model calls instead of a model."""

    name = "cassette"

    def __init__(self, calls: Iterable[ModelCall]) -> None:
        self._unplayed: defaultdict[str, list[ModelCall]] = defaultdict(list)
        for call in calls:
            asked = key(call.model, call.effort, call.system, call.prompt, answer_schema(call.kind))
            self._unplayed[asked].append(call)

    @staticmethod
    def calls_beside(events: Path) -> Path:
        """Where `mm play --out` keeps the model calls of the game it saved at `events`."""
        return events.with_suffix(".calls.ndjson")

    @classmethod
    def serving(cls, calls: Iterable[ModelCall]) -> Mapping[str, ModelProvider]:
        """One cassette standing in for every provider a game's lineup names."""
        cassette = cls(calls)
        return defaultdict(lambda: cassette)

    async def complete(self, request: ModelRequest) -> ModelReply:
        asked = key(request.model, request.effort, request.system, request.prompt, request.schema)
        if not self._unplayed[asked]:
            raise CassetteMissError(
                f"the cassette holds no answer to request {asked[:12]}, so a prompt or the game "
                "changed since it was recorded: re-record it (see docs/providers.md)"
            )
        return self._unplayed[asked].pop(0).as_reply()
