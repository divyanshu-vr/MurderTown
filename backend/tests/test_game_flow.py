"""Seam 1: a game setup plus one decision source per Resident goes in, an event log comes out."""

from mm.agents import scripted_bots
from mm.engine import GameConfig, Phase, Side
from mm.engine.events import AttackThwarted, GameEnded, PhaseStarted, ResidentDied, StatementMade
from mm.orchestrator import play_game
from tests.support import Asked, Requests, payloads, state_before, wrapped


async def test_a_scripted_game_ends_with_exactly_one_winner_as_its_last_event() -> None:
    result = await play_game(GameConfig(seed=7), scripted_bots(seed=7))

    endings = [event for event in result.events if isinstance(event.payload, GameEnded)]

    assert len(endings) == 1
    assert result.events[-1] == endings[0]
    assert endings[0].payload.winner in (Side.TOWN, Side.MURDERERS)


async def test_the_game_opens_with_a_night_whose_news_the_first_dawn_tells() -> None:
    result = await play_game(GameConfig(seed=3, max_days=4), scripted_bots(seed=3))

    starts = [i for i, event in enumerate(result.events) if isinstance(event.payload, PhaseStarted)]
    phases = [(result.events[i].payload.day, result.events[i].payload.phase) for i in starts]

    assert phases[:2] == [(1, Phase.NIGHT), (2, Phase.DAWN)]
    news = result.events[starts[1] + 1].payload
    assert isinstance(news, ResidentDied | AttackThwarted)


async def test_every_living_resident_makes_exactly_one_statement_in_each_opening_round() -> None:
    result = await play_game(GameConfig(seed=3, max_days=4), scripted_bots(seed=3))

    for day in (2, 3, 4):
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


async def test_every_decision_a_resident_makes_leaves_its_mark_in_the_log() -> None:
    asked: Requests = []
    config = GameConfig(seed=7, max_days=4)

    result = await play_game(config, wrapped(scripted_bots(config.seed), lambda b: Asked(b, asked)))

    ids = {request.id for request, _ in asked}
    assert ids == {event.decision_id for event in result.events if event.decision_id}
