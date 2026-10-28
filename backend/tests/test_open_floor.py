"""Seam 1: the Open floor. Bids, who speaks, and the three limits that end it."""

import pytest

from mm.engine import GameConfig
from mm.engine.decisions import DecisionRequest, Statement
from mm.engine.events import BidPlaced, Event, GameEnded, OpenFloorTimedOut, StatementMade
from mm.engine.perception import perceived_by
from mm.engine.state import GameState
from mm.orchestrator import play_game
from tests.support import (
    BidRule,
    StatementRule,
    keen,
    may_perceive,
    name_at_seat,
    payloads,
    puppets,
    seat_of,
    ticking,
)

CONFIG = GameConfig(residents=8, murderers=2, max_days=1, seed=4, open_floor_seconds=None)


def open_floor(events: list[Event]) -> list[StatementMade]:
    return [s for s in payloads(events, StatementMade, day=1) if s.part == "open_floor"]


async def test_the_open_floor_stops_at_its_statement_cap() -> None:
    result = await play_game(CONFIG, puppets(bids=keen))

    assert len(open_floor(result.events)) == CONFIG.open_floor_statements == 8


async def test_the_open_floor_ends_after_two_turns_in_which_nobody_bids() -> None:
    result = await play_game(CONFIG, puppets())

    assert open_floor(result.events) == []
    assert len(payloads(result.events, BidPlaced, day=1)) == 2 * CONFIG.residents


def bidding(by_seat: dict[int, int]) -> BidRule:
    """Bids by seat; every seat not listed bids 0."""

    def bid(name: str, known: GameState) -> int:
        return by_seat.get(seat_of(known)[name], 0)

    return bid


def addressing(seat: int) -> StatementRule:
    """Every Statement addresses the Resident in `seat`, who addresses nobody."""

    def say(request: DecisionRequest, known: GameState) -> Statement:
        return Statement.plain("Answer me, you!", addressed=[known.residents[seat].name])

    return say


def last_opening_statement(events: list[Event]) -> StatementMade:
    return [s for s in payloads(events, StatementMade, day=1) if s.part == "opening_round"][-1]


@pytest.mark.parametrize(
    ("bids", "addressed", "possible_speakers"),
    [
        pytest.param({0: 1, 1: 1, 2: 1, 3: 4}, None, {3}, id="the single highest bid speaks"),
        pytest.param({1: 2, 2: 3}, 1, {2}, id="a higher bid beats being addressed"),
        pytest.param({1: 3, 2: 3}, None, {1, 2}, id="a tie is won by one of the tied"),
        pytest.param({1: 3, 2: 3}, 1, {1, 2}, id="an addressed tie is still won by the tied"),
        pytest.param({}, None, set(), id="nobody speaks when every bid is 0"),
    ],
)
async def test_who_makes_the_first_statement_on_the_open_floor(
    bids: dict[int, int], addressed: int | None, possible_speakers: set[int]
) -> None:
    says = addressing(addressed) if addressed is not None else None

    result = await play_game(CONFIG, puppets(bids=bidding(bids), says=says))

    if addressed is not None:
        assert last_opening_statement(result.events).addressed == (
            name_at_seat(result.events, addressed),
        )
    statements = open_floor(result.events)
    if possible_speakers:
        possible = {name_at_seat(result.events, seat) for seat in possible_speakers}
        assert statements[0].speaker in possible
    else:
        assert statements == []


async def share_of_ties_won_by_seat_one(says: StatementRule | None) -> float:
    """Over 300 seeds, how often seat 1 wins a tie with seat 2 for the first Open-floor turn.

    Only games where the last opening Statement addressed exactly what `says`
    intended count: seat 1 if `says` addresses it, nobody otherwise.
    """
    wins = ties = 0
    for seed in range(300):
        config = CONFIG.model_copy(update={"seed": seed})
        result = await play_game(config, puppets(bids=bidding({1: 3, 2: 3}), says=says))
        seat_one = name_at_seat(result.events, 1)
        if last_opening_statement(result.events).addressed == ((seat_one,) if says else ()):
            ties += 1
            wins += open_floor(result.events)[0].speaker == seat_one
    assert ties > 200
    return wins / ties


async def test_a_tie_is_won_three_times_in_four_by_whoever_the_last_statement_addressed() -> None:
    assert 0.67 < await share_of_ties_won_by_seat_one(addressing(1)) < 0.83


async def test_a_tie_nobody_was_addressed_in_is_an_even_draw() -> None:
    assert 0.42 < await share_of_ties_won_by_seat_one(None) < 0.58


async def test_the_open_floor_stops_when_its_time_is_up_and_everyone_hears_so() -> None:
    config = CONFIG.model_copy(update={"open_floor_seconds": 300})

    result = await play_game(config, puppets(bids=keen), clock=ticking(200))

    assert len(open_floor(result.events)) == 1
    timed_out = next(e for e in result.events if isinstance(e.payload, OpenFloorTimedOut))
    assert all(may_perceive(timed_out, r.name) for r in result.state.residents)


async def test_each_bid_is_perceived_only_by_its_bidder() -> None:
    result = await play_game(CONFIG, puppets(bids=keen))

    for resident in result.state.residents:
        bids = payloads(perceived_by(result.events, resident.name), BidPlaced)
        assert bids
        assert {bid.resident for bid in bids} == {resident.name}


async def test_a_long_statement_is_cut_to_ninety_words() -> None:
    def rambles(request: DecisionRequest, known: GameState) -> Statement:
        return Statement.plain(" ".join(["blah"] * 150))

    result = await play_game(CONFIG, puppets(says=rambles))

    text = payloads(result.events, StatementMade)[0].text
    assert text.endswith("...")
    assert len(text.removesuffix("...").split()) == 90


async def test_a_statement_records_only_real_residents_other_than_the_speaker() -> None:
    def names_everyone(request: DecisionRequest, known: GameState) -> Statement:
        others = [r.name for r in known.residents if r.name != request.resident]
        names = ["Nobody", request.resident, others[0], others[0]]
        return Statement.plain("Listen.", addressed=names)

    result = await play_game(CONFIG, puppets(says=names_everyone))

    for statement in payloads(result.events, StatementMade):
        assert len(statement.addressed) == 1
        assert statement.addressed[0] != statement.speaker
        assert statement.addressed[0] in {r.name for r in result.state.residents}


async def test_a_game_where_everyone_stays_quiet_and_skips_still_ends() -> None:
    config = CONFIG.model_copy(update={"max_days": 10})

    result = await play_game(config, puppets())

    assert isinstance(result.events[-1].payload, GameEnded)
