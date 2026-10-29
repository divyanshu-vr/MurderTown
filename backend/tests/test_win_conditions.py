"""Seam 1: how a game ends."""

from mm.engine import GameConfig, Role, Side
from mm.engine.events import GameEnded, PhaseStarted, RoleAssigned, RolesRevealed
from mm.engine.perception import perceived_by
from mm.orchestrator import play_game
from tests.support import Script, everyone_votes_for, payloads, puppets, seats_by_role

SIX_RESIDENTS = GameConfig(residents=6, murderers=1, max_days=5, seed=2)


async def test_the_town_wins_the_moment_the_last_murderer_is_banished() -> None:
    (murderer,) = seats_by_role(SIX_RESIDENTS)[Role.MURDERER]

    result = await play_game(SIX_RESIDENTS, puppets({2: everyone_votes_for(murderer)}))

    (ending,) = payloads(result.events, GameEnded)
    assert ending.winner is Side.TOWN
    assert max(start.day for start in payloads(result.events, PhaseStarted)) == 2


async def test_the_murderers_win_once_they_equal_the_rest_of_the_town() -> None:
    (murderer,) = seats_by_role(SIX_RESIDENTS)[Role.MURDERER]
    town = [seat for seat in range(6) if seat != murderer]
    banish: Script = {2: everyone_votes_for(town[0]), 3: everyone_votes_for(town[2])}
    nights = {"kills": {1: town[0], 2: town[1], 3: town[3]},  # the first Victim is saved
              "protects": {1: town[0], 2: murderer, 3: town[4]}}  # fmt: skip

    result = await play_game(SIX_RESIDENTS, puppets(banish, **nights))

    (ending,) = payloads(result.events, GameEnded)
    assert ending.winner is Side.MURDERERS
    assert ending.reason == "The Murderers now equal the rest of the town."
    assert len(result.state.living) == 2


async def test_the_murderers_win_when_the_town_runs_out_of_days() -> None:
    result = await play_game(SIX_RESIDENTS.model_copy(update={"max_days": 2}), puppets())

    (ending,) = payloads(result.events, GameEnded)
    assert ending.winner is Side.MURDERERS
    assert ending.reason == "The town ran out of days."
    assert result.events[-1].day == 2


async def test_as_a_side_wins_every_resident_learns_every_role() -> None:
    (murderer,) = seats_by_role(SIX_RESIDENTS)[Role.MURDERER]

    result = await play_game(SIX_RESIDENTS, puppets({2: everyone_votes_for(murderer)}))

    *_, reveal, ending = result.events
    assert isinstance(ending.payload, GameEnded)
    assert isinstance(reveal.payload, RolesRevealed)
    assigned = {role.resident: role.role for role in payloads(result.events, RoleAssigned)}
    assert reveal.payload.roles == assigned
    for resident in result.state.residents:
        assert reveal in perceived_by(result.events, resident.name)
