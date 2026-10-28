"""The recorded game the console's tests replay shows every kind of event, so they can test each.

Except two, which the console's tests add to the recorded game themselves: a game that
ends with a winner was never aborted (and scripted Residents never fail), and `mm play`
records games with no time limit on the Open floor, so it never runs out of time.
"""

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

    assert recorded == every_event_type() - {"game_aborted", "open_floor_timed_out"}
