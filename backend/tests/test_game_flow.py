"""Seam 1: a game setup plus one decision source per Resident goes in, an event log comes out."""

from collections.abc import Sequence

from mm.agents import Brain, scripted_bots
from mm.engine import GameConfig, Phase, Side
from mm.engine.decisions import Answer, DecisionRequest
from mm.engine.events import Event, GameEnded, PhaseStarted, StatementMade
from mm.orchestrator import play_game
from tests.support import payloads, state_before, wrapped


async def test_a_scripted_game_ends_with_exactly_one_winner_as_its_last_event() -> None:
    result = await play_game(GameConfig(seed=7), scripted_bots(seed=7))

    endings = [event for event in result.events if isinstance(event.payload, GameEnded)]

    assert len(endings) == 1
    assert result.events[-1] == endings[0]
    assert endings[0].payload.winner in (Side.TOWN, Side.MURDERERS)


async def test_every_living_resident_makes_exactly_one_statement_in_each_opening_round() -> None:
    result = await play_game(GameConfig(seed=3, max_days=3), scripted_bots(seed=3))

    for day in (1, 2, 3):
        discussion_starts = state_before(
            result.events,
            lambda event, day=day: (
                isinstance(event.payload, PhaseStarted)
                and event.payload.day == day
                and event.payload.phase is Phase.DISCUSSION
            ),
        )
        speakers = [
            statement.speaker
            for statement in payloads(result.events, StatementMade, day=day)
            if statement.part == "opening_round"
        ]
        assert sorted(speakers) == sorted(discussion_starts.living)


class Asked:
    """Passes every request on, noting the id of each decision a Resident is asked for."""

    def __init__(self, inner: Brain, ids: set[str]) -> None:
        self.inner, self.ids = inner, ids

    async def decide(self, request: DecisionRequest, view: Sequence[Event]) -> Answer:
        self.ids.add(request.id)
        return await self.inner.decide(request, view)


async def test_every_decision_a_resident_makes_leaves_its_mark_in_the_log() -> None:
    asked: set[str] = set()
    config = GameConfig(seed=7, max_days=4)

    result = await play_game(config, wrapped(scripted_bots(config.seed), lambda b: Asked(b, asked)))

    assert asked == {event.decision_id for event in result.events if event.decision_id}
