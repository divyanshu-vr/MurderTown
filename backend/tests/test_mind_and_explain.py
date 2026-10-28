"""Transport: the Mind inspector's endpoints, read the way the browser reads them.

The mind endpoint shows one Resident's mind as of a moment in the game; the
explain endpoint shows the model attempts behind the decision that caused an event.
"""

from collections.abc import Callable, Iterator
from typing import Any

import pytest
from fastapi.testclient import TestClient

from mm.engine.decisions import DecisionKind, Suspicion
from mm.engine.events import (
    BallotCast,
    Event,
    GameStarted,
    Payload,
    PhaseStarted,
    ReflectionWritten,
    RoleAssigned,
    StatementMade,
)
from mm.llm import ModelReply, ModelRequest
from mm.orchestrator.narrator import NARRATOR
from tests.conftest import played_to_the_end, serving
from tests.support import (
    FakeModel,
    agents_on,
    answer_kind,
    may_perceive,
    model_answer,
    sensible_answer,
)

CONFIG = {"residents": 8, "murderers": 2, "max_days": 2, "seed": 4}


def finished_game(client: TestClient, config: dict[str, Any] = CONFIG) -> tuple[str, list[Event]]:
    game_id = played_to_the_end(client, config)
    events = client.get(f"/games/{game_id}/events").json()["events"]
    return game_id, [Event.model_validate(event) for event in events]


def first[P: Payload](
    events: list[Event], kind: type[P], where: Callable[[P], bool] = lambda _: True
) -> tuple[Event, P]:
    """The first event of a kind (that meets a condition), with its payload."""
    for event in events:
        if isinstance(event.payload, kind) and where(event.payload):
            return event, event.payload
    raise AssertionError(f"no {kind.__name__} in the log")


def test_a_mind_holds_only_the_notes_written_up_to_the_moment_viewed(client: TestClient) -> None:
    game_id, events = finished_game(client)
    event, notes = first(events, ReflectionWritten, lambda notes: bool(notes.notebook))
    url = f"/games/{game_id}/residents/{notes.resident}/mind"

    before = client.get(url, params={"at": event.seq - 1}).json()
    after = client.get(url, params={"at": event.seq}).json()

    assert before["memory"]["notebook"] == ""
    assert after["memory"]["notebook"] == notes.notebook
    assert after["memory"]["journal"][-1]["text"] == notes.journal_entry
    assert max(perceived["seq"] for perceived in after["perceived"]) == event.seq


def test_a_mind_shows_the_residents_own_role_and_only_what_they_perceived(
    client: TestClient,
) -> None:
    game_id, events = finished_game(client)
    _, assigned = first(events, RoleAssigned)

    mind = client.get(f"/games/{game_id}/residents/{assigned.resident}/mind").json()

    assert (mind["role"], mind["persona"]["quirk"]) == (assigned.role, assigned.persona.quirk)
    perceived = [Event.model_validate(event) for event in mind["perceived"]]
    assert all(may_perceive(event, assigned.resident) for event in perceived)
    assert len(perceived) < len(events)


@pytest.mark.parametrize(("stranger", "at"), [(True, None), (False, 1)])
def test_there_is_no_mind_for_a_stranger_or_before_roles_are_given(
    client: TestClient, stranger: bool, at: int | None
) -> None:
    game_id, events = finished_game(client)
    name = "Nobody" if stranger else first(events, RoleAssigned)[1].resident

    moment = {"at": at} if at else {}
    response = client.get(f"/games/{game_id}/residents/{name}/mind", params=moment)

    assert response.status_code == 404


def test_a_scripted_decision_is_explained_with_no_model_attempts(client: TestClient) -> None:
    game_id, events = finished_game(client)
    ballot, _ = first(events, BallotCast)

    explained = client.get(f"/games/{game_id}/events/{ballot.seq}/explain").json()

    assert explained["attempts"] == []
    assert explained["event"]["seq"] == ballot.seq


def test_an_event_no_decision_caused_has_nothing_to_explain(client: TestClient) -> None:
    game_id, events = finished_game(client)
    phase, _ = first(events, PhaseStarted)

    assert client.get(f"/games/{game_id}/events/{phase.seq}/explain").status_code == 404


def leaky_first_ballots(request: ModelRequest) -> ModelReply:
    """Ballots name an email first and SKIP when retried; every Statement is refused."""
    match answer_kind(request):
        case DecisionKind.BALLOT if "could not be used" not in request.prompt:
            return model_answer({"target": "host@example.com", "reason": "a hunch"})
        case DecisionKind.STATEMENT:
            return ModelReply(outcome="refusal", data=None, text="", error="the model declined")
        case _:
            return sensible_answer(request)


@pytest.fixture
def agents_client(database_url: str) -> Iterator[TestClient]:
    with serving(database_url, agents_on(FakeModel(leaky_first_ballots))) as test_client:
        yield test_client


def test_an_explanation_shows_every_attempt_with_outside_details_hidden(
    agents_client: TestClient,
) -> None:
    game_id, events = finished_game(agents_client)
    ballot, _ = first(events, BallotCast)

    response = agents_client.get(f"/games/{game_id}/events/{ballot.seq}/explain")

    attempts = response.json()["attempts"]
    assert [attempt["outcome"] for attempt in attempts] == ["invalid", "ok"]
    assert {attempt["decision_id"] for attempt in attempts} == {ballot.decision_id}
    assert attempts[0]["system"]
    assert "is not one of the options" in attempts[1]["prompt"]
    assert response.json()["fallback_reason"] is None
    assert "host@example.com" not in response.text
    assert "[hidden]" in response.text


def test_an_explanation_gives_the_reason_a_decision_fell_back(agents_client: TestClient) -> None:
    game_id, events = finished_game(agents_client)
    statement, _ = first(events, StatementMade)

    explained = agents_client.get(f"/games/{game_id}/events/{statement.seq}/explain").json()

    assert [attempt["outcome"] for attempt in explained["attempts"]] == ["refusal"]
    assert explained["fallback_reason"] == "the model declined"


def test_each_game_explains_its_decisions_with_its_own_model_calls(
    agents_client: TestClient,
) -> None:
    finished_game(agents_client)
    game_id, events = finished_game(agents_client, {**CONFIG, "seed": 5})
    residents = {resident.name for resident in first(events, GameStarted)[1].residents}
    deciders = residents | {NARRATOR.name}

    for event in events:
        if event.decision_id:
            explained = agents_client.get(f"/games/{game_id}/events/{event.seq}/explain").json()
            assert explained["attempts"]
            assert {attempt["resident"] for attempt in explained["attempts"]} <= deciders


def changed_suspicion(events: list[Event]) -> tuple[int, str, Suspicion, Suspicion]:
    """A reflection that changes a suspicion its writer recorded earlier.

    Returns its sequence number, its writer, and the suspicion before and after.
    """
    latest: dict[tuple[str, str], Suspicion] = {}
    for event in events:
        if isinstance(notes := event.payload, ReflectionWritten):
            for suspicion in notes.suspicions:
                about = (notes.resident, suspicion.resident)
                if about in latest and latest[about] != suspicion:
                    return event.seq, notes.resident, latest[about], suspicion
                latest[about] = suspicion
    raise AssertionError("no Resident changed a suspicion")


def test_a_minds_dossier_holds_the_latest_suspicion_about_each_resident(client: TestClient) -> None:
    game_id, events = finished_game(client)
    seq, writer, old, new = changed_suspicion(events)
    url = f"/games/{game_id}/residents/{writer}/mind"

    before = client.get(url, params={"at": seq - 1}).json()["memory"]["dossier"]
    after = client.get(url, params={"at": seq}).json()["memory"]["dossier"]

    assert old.model_dump() in before
    assert new.model_dump() in after
    assert old.model_dump() not in after
