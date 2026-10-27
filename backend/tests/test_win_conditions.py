"""Seam 1: how a game ends."""

from mm.engine import GameConfig, Role, Side
from mm.engine.events import GameEnded, PhaseStarted
from mm.orchestrator import play_game
from tests.support import Script, payloads, puppets, seats_by_role

SIX_RESIDENTS = GameConfig(residents=6, murderers=1, max_days=5, seed=2)


def everyone_votes_for(target: int, seats: range = range(6)) -> dict[int, int | None]:
    """The target abstains, because nobody may vote for themselves."""
    return {seat: target for seat in seats if seat != target}


async def test_the_town_wins_the_moment_the_last_murderer_is_banished() -> None:
    (murderer,) = (await seats_by_role(SIX_RESIDENTS))[Role.MURDERER]

    result = await play_game(SIX_RESIDENTS, puppets({1: everyone_votes_for(murderer)}))

    (ending,) = payloads(result.events, GameEnded)
    assert ending.winner is Side.TOWN
    assert max(start.day for start in payloads(result.events, PhaseStarted)) == 1


async def test_the_murderers_win_once_they_equal_the_rest_of_the_town() -> None:
    (murderer,) = (await seats_by_role(SIX_RESIDENTS))[Role.MURDERER]
    town = [seat for seat in range(6) if seat != murderer]
    script: Script = {day: everyone_votes_for(town[day - 1]) for day in range(1, 5)}

    result = await play_game(SIX_RESIDENTS, puppets(script))

    (ending,) = payloads(result.events, GameEnded)
    assert ending.winner is Side.MURDERERS
    assert result.events[-1].day == 4


async def test_the_murderers_win_when_the_town_runs_out_of_days() -> None:
    result = await play_game(SIX_RESIDENTS.model_copy(update={"max_days": 2}), puppets())

    (ending,) = payloads(result.events, GameEnded)
    assert ending.winner is Side.MURDERERS
    assert ending.reason == "The town ran out of days."
    assert result.events[-1].day == 2
