"""The protocol between backend and frontend, exported as one JSON Schema document.

The backend's Pydantic models are the single definition of the protocol. The
frontend generates its TypeScript types from this schema, so the two cannot drift.
"""

from typing import Any

from pydantic.json_schema import models_json_schema

from mm.agents.memory import Mind
from mm.api.routes import (
    CallPage,
    CostReport,
    EventPage,
    Explanation,
    GameCreated,
    GameList,
    GameSummary,
    SetupChoices,
)
from mm.engine import GameConfig
from mm.engine.events import Event
from mm.review import Review


def protocol_schema() -> dict[str, Any]:
    """The protocol as JSON Schema, with per-field titles removed.

    Pydantic titles every field; code generators would turn each title into its
    own type alias, so only the model-level titles (which name the types) are kept.
    A model the server both accepts and sends, like `GameConfig`, appears twice:
    as sent, with every field present, and as accepted, where defaults may be
    left out. The accepted form is named `<Model>Input`. Its seed has no default: the
    server draws one when the Host leaves it out, since a known seed would tell every role.
    A tuple whose items are all of one type, like a Conversation's pair, is written as an array of
    that type with its length fixed: the TypeScript generator reads `prefixItems` as a tuple of
    unknowns, but this as a tuple of that type.
    """
    _, schema = models_json_schema(
        [
            (Event, "serialization"),
            (EventPage, "serialization"),
            (GameSummary, "serialization"),
            (GameList, "serialization"),
            (SetupChoices, "serialization"),
            (GameCreated, "serialization"),
            (Mind, "serialization"),
            (Explanation, "serialization"),
            (CostReport, "serialization"),
            (CallPage, "serialization"),
            (Review, "serialization"),
            (GameConfig, "validation"),
        ],
        title="MurderTown protocol",
    )
    accepted_seed = schema["$defs"]["GameConfig-Input"]["properties"]["seed"]
    del accepted_seed["default"]
    accepted_seed["description"] = "Left out, the server draws one at random."
    for name, definition in schema["$defs"].items():
        if name.endswith("-Input"):
            definition["title"] += "Input"
        for field in definition.get("properties", {}).values():
            field.pop("title", None)
    _tuples_of_one_type(schema)
    return schema


def _tuples_of_one_type(node: Any) -> None:
    if isinstance(node, dict):
        items = node.get("prefixItems")
        if isinstance(items, list) and _all_alike(items) and "items" not in node:
            node["items"] = node.pop("prefixItems")[0]
            node["minItems"] = node["maxItems"] = len(items)
        for value in node.values():
            _tuples_of_one_type(value)
    elif isinstance(node, list):
        for value in node:
            _tuples_of_one_type(value)


def _all_alike(items: list[Any]) -> bool:
    return bool(items) and all(item == items[0] for item in items)
