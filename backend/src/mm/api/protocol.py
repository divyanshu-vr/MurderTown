"""The protocol between backend and frontend, exported as one JSON Schema document.

The backend's Pydantic models are the single definition of the protocol. The
frontend generates its TypeScript types from this schema, so the two cannot drift.
"""

from typing import Any

from pydantic.json_schema import models_json_schema

from mm.api.routes import EventPage, GameCreated, GameSummary
from mm.engine import GameConfig
from mm.engine.events import Event


def protocol_schema() -> dict[str, Any]:
    """The protocol as JSON Schema, with per-field titles removed.

    Pydantic titles every field; code generators would turn each title into its
    own type alias, so only the model-level titles (which name the types) are kept.
    """
    _, schema = models_json_schema(
        [
            (Event, "serialization"),
            (EventPage, "serialization"),
            (GameSummary, "serialization"),
            (GameCreated, "serialization"),
            (GameConfig, "validation"),
        ],
        title="MurderTown protocol",
    )
    for definition in schema["$defs"].values():
        for field in definition.get("properties", {}).values():
            field.pop("title", None)
    return schema
