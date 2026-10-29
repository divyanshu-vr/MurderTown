"""Seam 1: the Sheriff's single bullet, fired in the Showdown or, if so set up, at Night."""

from mm.engine import GameConfig, Phase, Role, Side
from mm.engine.events import (
    Event,
    GameEnded,
    PhaseStarted,
    ResidentDied,
    SheriffFired,
    SheriffHeldFire,
)
from mm.orchestrator import play_game
from tests.support import everyone_alive_on_day_two, name_at_seat, payloads, puppets, seats_by_role

CONFIG = GameConfig(residents=8, murderers=2, max_days=4, seed=9, open_floor_seconds=None)


def showdown_days(events: list[Event]) -> list[int]:
    return [p.day for p in payloads(events, PhaseStarted) if p.phase is Phase.SHOWDOWN]


def deaths(events: list[Event]) -> list[tuple[str, str]]:
    """Who died on Day 2, the first with a Showdown, and how. Its Dawn announces the first
    Night's murder, so tests that look here have the Doctor save that Night's Victim."""
    return [(d.resident, d.cause) for d in payloads(events, ResidentDied, day=2)]


async def test_a_sheriff_who_hits_a_murderer_kills_only_the_murderer() -> None:
    roles = seats_by_role(CONFIG)
    murderer = roles[Role.MURDERER][0]

    result = await play_game(
        CONFIG, puppets(shots={2: murderer}, **everyone_alive_on_day_two(CONFIG))
    )

    (shot,) = payloads(result.events, SheriffFired)
    assert shot.hit_a_murderer
    assert deaths(result.events) == [(name_at_seat(result.events, murderer), "shot")]


async def test_shooting_the_last_murderer_wins_the_game_before_the_vote() -> None:
    config = CONFIG.model_copy(update={"residents": 6, "murderers": 1})
    roles = seats_by_role(config)
    (murderer,) = roles[Role.MURDERER]

    result = await play_game(
        config, puppets(shots={2: murderer}, **everyone_alive_on_day_two(config))
    )

    (ending,) = payloads(result.events, GameEnded)
    assert ending.winner is Side.TOWN
    assert Phase.VOTE not in {p.phase for p in payloads(result.events, PhaseStarted)}


async def test_a_sheriff_who_hits_a_town_resident_dies_of_the_backfire() -> None:
    roles = seats_by_role(CONFIG)
    (sheriff,) = roles[Role.SHERIFF]
    civilian = roles[Role.CIVILIAN][0]

    result = await play_game(
        CONFIG, puppets(shots={2: civilian}, **everyone_alive_on_day_two(CONFIG))
    )

    assert deaths(result.events) == [
        (name_at_seat(result.events, civilian), "shot"),
        (name_at_seat(result.events, sheriff), "backfire"),
    ]


async def test_the_bullet_can_be_fired_only_once_per_game() -> None:
    roles = seats_by_role(CONFIG)
    (first, second) = roles[Role.MURDERER]

    result = await play_game(
        CONFIG, puppets(shots={2: first, 3: second}, **everyone_alive_on_day_two(CONFIG))
    )

    assert len(payloads(result.events, SheriffFired)) == 1
    assert showdown_days(result.events) == [2]


async def test_a_sheriff_who_holds_fire_keeps_the_bullet_for_another_day() -> None:
    result = await play_game(CONFIG, puppets())

    assert payloads(result.events, SheriffFired) == []
    assert showdown_days(result.events) == [2, 3, 4]


async def test_without_a_sheriff_there_is_no_showdown() -> None:
    result = await play_game(CONFIG.model_copy(update={"sheriff": False}), puppets())

    assert showdown_days(result.events) == []


async def test_the_night_setting_moves_the_shot_to_night_but_not_the_opening_one() -> None:
    config = CONFIG.model_copy(update={"sheriff_shoots_at": "night"})
    murderer = seats_by_role(config)[Role.MURDERER][0]
    scripted = puppets(shots={1: murderer, 2: murderer}, **everyone_alive_on_day_two(config))

    result = await play_game(config, scripted)

    assert showdown_days(result.events) == []
    asked = [e for e in result.events if isinstance(e.payload, SheriffFired | SheriffHeldFire)]
    assert [(e.day, e.phase) for e in asked] == [(2, Phase.NIGHT)]  # nothing to go on before


async def test_holding_fire_is_recorded_for_spectators_and_perceived_by_no_resident() -> None:
    result = await play_game(CONFIG, puppets())

    holds = [e for e in result.events if isinstance(e.payload, SheriffHeldFire)]
    assert [e.day for e in holds] == showdown_days(result.events)
    assert all(e.visibility.scope == "spectators" for e in holds)
