"""What a game is expected to cost before it starts: how long the paper game runs, the share of
each model, and how close the estimate comes to a recorded live game's cost."""

from pathlib import Path

import pytest

from mm.agents import ModelCall
from mm.agents.estimate import DEFAULT_MODEL, MEASURED, SEATINGS, estimate
from mm.cli.recording import read_ndjson
from mm.engine import GameConfig, Lineup, PlayedBy, Role
from mm.engine.casting import seated_roles
from mm.engine.decisions import DecisionKind
from mm.engine.events import Event, GameConfigured

ON_HAIKU = PlayedBy(provider="claude", model="claude-haiku-5-5")
ON_SONNET = PlayedBy(provider="claude", model="claude-sonnet-5-5")
FIXTURES = Path(__file__).parents[2] / "fixtures"


@pytest.mark.parametrize(
    ("rules", "days"),
    [
        # 5 Town: a Night (4), Day 2's Vote and Night (2), then Day 3's Vote banishes the Murderer
        pytest.param({"residents": 6, "murderers": 1}, 3, id="six Residents, one Murderer"),
        # 9 Town, 3 Murderers. Night 1: 8 Town. Day 2 banishes Town: 7, Night: 6. Day 3 banishes
        # a Murderer: 2, Night: 5. Day 4: 4, then 3. Day 5: 1 Murderer, then 2 Town. Day 6's
        # Vote leaves 1 Town, as many as the Murderers.
        pytest.param({"residents": 12, "murderers": 3}, 6, id="twelve Residents, three Murderers"),
        pytest.param({"residents": 12, "murderers": 3, "max_days": 2}, 2, id="cut short"),
    ],
)
def test_the_paper_game_runs_until_a_side_wins_or_the_days_run_out(
    rules: dict[str, int], days: int
) -> None:
    assert estimate(GameConfig(lineup=Lineup(everyone=ON_HAIKU), **rules)).days == days


def test_each_model_has_its_share_and_sonnet_murderers_cost_more() -> None:
    haiku = estimate(GameConfig(lineup=Lineup(everyone=ON_HAIKU)))
    mixed = estimate(GameConfig(lineup=Lineup(everyone=ON_HAIKU, murderers=ON_SONNET)))

    assert set(haiku.by_model) == {ON_HAIKU.model}
    assert set(mixed.by_model) == {ON_HAIKU.model, ON_SONNET.model}
    assert mixed.usd > haiku.usd
    assert mixed.usd == pytest.approx(sum(mixed.by_model.values()))


def test_every_decision_kind_has_measured_tokens_to_price_it_by() -> None:
    assert set(MEASURED[DEFAULT_MODEL]) == set(DecisionKind)


def test_a_setup_with_no_seed_is_priced_over_every_seating() -> None:
    lineup = Lineup(everyone=ON_HAIKU, seats={0: ON_SONNET})
    roles_of_seat_0 = {seed: seated_roles(GameConfig(seed=seed))[0] for seed in range(SEATINGS)}
    murderer = next(seed for seed, role in roles_of_seat_0.items() if role is Role.MURDERER)
    civilian = next(seed for seed, role in roles_of_seat_0.items() if role is Role.CIVILIAN)

    def sonnet_share(seed: int, seeded: bool = True) -> float:
        config = GameConfig(lineup=lineup, seed=seed)
        return estimate(config, seeded=seeded).by_model[ON_SONNET.model]

    shares = sonnet_share(civilian), sonnet_share(murderer)
    assert min(shares) < sonnet_share(0, seeded=False) < max(shares)


def test_a_scripted_game_costs_nothing() -> None:
    assert estimate(GameConfig()).usd == 0


def test_the_estimate_comes_near_what_the_recorded_live_game_cost() -> None:
    events = read_ndjson(FIXTURES / "live-game.ndjson", Event)
    (configured,) = [e.payload for e in events if isinstance(e.payload, GameConfigured)]
    calls = read_ndjson(FIXTURES / "live-game.calls.ndjson", ModelCall)

    spent = sum(call.cost_usd for call in calls)

    assert estimate(configured.config).usd == pytest.approx(spent, rel=0.5)
