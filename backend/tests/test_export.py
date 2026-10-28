"""`mm export`: a finished game's whole log, as a game file the console replays with no server."""

import json
from pathlib import Path

from typer.testing import CliRunner

from mm.agents import ModelCall
from mm.cli import app
from mm.cli.recording import calls_beside, read_ndjson, review_beside
from mm.engine.events import Event
from tests.conftest import played_to_the_end, serving, start_game
from tests.support import FakeModel, agents_on, unhurried_bots

CONFIG = {"residents": 6, "murderers": 1, "max_days": 2, "seed": 4}


def export(database_url: str, game_id: str, out: Path) -> tuple[int, str]:
    result = CliRunner().invoke(
        app, ["export", game_id, "--out", str(out)], env={"MM_DATABASE_URL": database_url}
    )
    return result.exit_code, result.output


def test_a_finished_game_is_written_whole_with_its_model_calls_and_review_beside_it(
    database_url: str, tmp_path: Path
) -> None:
    with serving(database_url, agents_on(FakeModel())) as client:
        game_id = played_to_the_end(client, CONFIG)
        stored = client.get(f"/games/{game_id}/events").json()["events"]
        calls_made = client.get(f"/games/{game_id}/cost").json()["total"]["calls"]
        reviewed = client.get(f"/games/{game_id}/review").json()
    out = tmp_path / "game.ndjson"

    code, output = export(database_url, game_id, out)

    assert code == 0, output
    assert [event.model_dump(mode="json") for event in read_ndjson(out, Event)] == stored
    assert len(read_ndjson(calls_beside(out), ModelCall)) == calls_made > 0
    assert json.loads(review_beside(out).read_text(encoding="utf-8")) == reviewed


def test_a_game_still_being_played_is_not_exported(database_url: str, tmp_path: Path) -> None:
    with serving(database_url, unhurried_bots) as client:
        game_id = start_game(client, CONFIG)
        assert client.post(f"/games/{game_id}/pause").status_code == 200
    out = tmp_path / "game.ndjson"

    code, output = export(database_url, game_id, out)

    assert code != 0
    assert "has not ended" in output
    assert not out.exists()
