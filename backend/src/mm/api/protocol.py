"""The protocol between backend and frontend, exported as one JSON Schema document.

The backend's Pydantic models are the single definition of the protocol. The
frontend generates its TypeScript types from this schema, so the two cannot drift.
"""

from typing import Any

from pydantic.json_schema import models_json_schema

from mm.agents.memory import Mind
from mm.api.routes import CostReport, EventPage, Explanation, GameCreated, GameSummary
from mm.engine import GameConfig
from mm.engine.events import Event


def protocol_schema() -> dict[str, Any]:
    """The protocol as JSON Schema, with per-field titles removed.

    Pydantic titles every field; code generators would turn each title into its
    own type alias, so only the model-level titles (which name the types) are kept.
    A model the server both accepts and sends, like `GameConfig`, appears twice:
    as sent, with every field present, and as accepted, where defaults may be
    left out. The accepted form is named `<Model>Input`.
    """
    _, schema = models_json_schema(
        [
            (Event, "serialization"),
            (EventPage, "serialization"),
            (GameSummary, "serialization"),
            (GameCreated, "serialization"),
            (Mind, "serialization"),
            (Explanation, "serialization"),
            (CostReport, "serialization"),
            (GameConfig, "validation"),
        ],
        title="MurderTown protocol",
    )
    for name, definition in schema["$defs"].items():
        if name.endswith("-Input"):
            definition["title"] += "Input"
        for field in definition.get("properties", {}).values():
            field.pop("title", None)
    return schema
