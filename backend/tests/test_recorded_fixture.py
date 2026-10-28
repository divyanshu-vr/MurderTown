"""The recorded game the console's tests replay shows every kind of event, so they can test each,
and its review beside it every kind of lie and turning point.

Except two, which the console's tests add to the recorded game themselves: a game that
ends with a winner was never aborted (and scripted Residents never fail), and `mm play`
records games with no time limit on the Open floor, so it never runs out of time.
"""

from pathlib import Path
from typing import get_args

from mm.cli.recording import read_ndjson, review_beside
from mm.engine.events import Event, EventPayload
from mm.review import Review, review_of

FIXTURE = Path(__file__).parents[2] / "fixtures" / "scripted-game.ndjson"


def every_event_type() -> set[str]:
    """The `type` of every payload in the protocol. EventPayload is Annotated[Union[...], ...]."""
    union = get_args(EventPayload)[0]
    return {payload.model_fields["type"].default for payload in get_args(union)}


def test_the_recorded_game_contains_every_event_type() -> None:
    lines = FIXTURE.read_text(encoding="utf-8").splitlines()
    recorded = {Event.model_validate_json(line).payload.type for line in lines}

    assert recorded == every_event_type() - {
        "decision_unanswered",
        "game_aborted",
        "open_floor_timed_out",
    }


def test_the_recorded_game_has_a_review_beside_it_with_every_kind_of_turning_point_and_lie() -> (
    None
):
    review = Review.model_validate_json(review_beside(FIXTURE).read_text(encoding="utf-8"))
    events = read_ndjson(FIXTURE, Event)
    kinds_at = {event.seq: event.payload.type for event in events}

    assert review == review_of(events)
    assert {lie.kind for lie in review.lies} == {
        "false_role",
        "accused_trusted",
        "defended_suspected",
    }
    turning = {kinds_at[p.seq] if p.kind == "event" else p.kind for p in review.turning_points}
    assert turning == {"resident_died", "sheriff_fired", "swing"}
    assert review.influence
