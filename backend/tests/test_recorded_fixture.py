"""The recorded game the console's tests replay shows every kind of event, so they can test each."""

from pathlib import Path
from typing import get_args

from mm.engine.events import Event, EventPayload

FIXTURE = Path(__file__).parents[2] / "fixtures" / "scripted-game.ndjson"


def every_event_type() -> set[str]:
    """The `type` of every payload in the protocol. EventPayload is Annotated[Union[...], ...]."""
    union = get_args(EventPayload)[0]
    return {payload.model_fields["type"].default for payload in get_args(union)}


def test_the_recorded_game_contains_every_event_type() -> None:
    lines = FIXTURE.read_text(encoding="utf-8").splitlines()
    recorded = {Event.model_validate_json(line).payload.type for line in lines}

    assert recorded == every_event_type()
