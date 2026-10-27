"""Seam 1: who is dealt which role, and who may perceive it."""

from collections import Counter
from collections.abc import Sequence

from mm.agents import Brain, scripted_bots
from mm.engine import GameConfig, Resident, Role
from mm.engine.decisions import Answer, DecisionRequest
from mm.engine.events import Event, RoleAssigned
from mm.engine.perception import perceived_by
from mm.orchestrator import play_game
from tests.support import payloads


async def test_the_roles_dealt_match_the_configuration() -> None:
    config = GameConfig(residents=12, murderers=2, seed=11, max_days=1)
    result = await play_game(config, scripted_bots(seed=11))

    dealt = Counter(assignment.role for assignment in payloads(result.events, RoleAssigned))

    assert dealt == {
        Role.MURDERER: 2,
        Role.DOCTOR: 1,
        Role.DETECTIVE: 1,
        Role.SHERIFF: 1,
        Role.CIVILIAN: 7,
    }


async def test_each_resident_perceives_only_their_own_role_assignment() -> None:
    result = await play_game(GameConfig(seed=11, max_days=1), scripted_bots(seed=11))

    for resident in result.state.residents:
        perceived = payloads(perceived_by(result.events, resident.name), RoleAssigned)
        assert [assignment.resident for assignment in perceived] == [resident.name]


async def test_murderers_learn_their_teammates_and_nobody_else_learns_any() -> None:
    config = GameConfig(residents=15, murderers=3, seed=5, max_days=1)
    result = await play_game(config, scripted_bots(seed=5))
    assignments = payloads(result.events, RoleAssigned)
    murderers = {a.resident for a in assignments if a.role is Role.MURDERER}

    for assignment in assignments:
        if assignment.role is Role.MURDERER:
            assert set(assignment.teammates) == murderers - {assignment.resident}
        else:
            assert assignment.teammates == ()


def may_perceive(event: Event, resident: str) -> bool:
    """The visibility rule, restated independently of the code under test."""
    scope = event.visibility.scope
    return scope == "everyone" or (scope == "residents" and resident in event.visibility.residents)


async def test_a_decision_source_is_only_ever_shown_what_its_resident_may_perceive() -> None:
    shown: list[tuple[str, list[Event]]] = []
    bots = scripted_bots(seed=17)

    class Watching:
        def __init__(self, inner: Brain) -> None:
            self.inner = inner

        async def decide(self, request: DecisionRequest, view: Sequence[Event]) -> Answer:
            shown.append((request.resident, list(view)))
            return await self.inner.decide(request, view)

    def make(resident: Resident) -> Brain:
        return Watching(bots(resident))

    await play_game(GameConfig(residents=10, murderers=2, max_days=3, seed=17), make)

    assert shown
    for resident, view in shown:
        assert all(may_perceive(event, resident) for event in view)
