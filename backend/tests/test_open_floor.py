"""Seam 1: the Open floor. Bids, who speaks, and the three limits that end it."""

from itertools import count

from mm.engine import GameConfig
from mm.engine.decisions import DecisionRequest, Statement
from mm.engine.events import BidPlaced, Event, GameEnded, StatementMade
from mm.engine.perception import perceived_by
from mm.engine.state import GameState
from mm.orchestrator import play_game
from tests.support import name_at_seat, payloads, puppets, saying, seat_of

CONFIG = GameConfig(residents=8, murderers=2, max_days=1, seed=4, open_floor_seconds=None)


def open_floor(events: list[Event]) -> list[StatementMade]:
    return [s for s in payloads(events, StatementMade, day=1) if s.part == "open_floor"]


def keen(name: str, known: GameState) -> int:
    return 2


async def test_the_open_floor_stops_at_its_statement_cap() -> None:
    result = await play_game(CONFIG, puppets(bids=keen))

    assert len(open_floor(result.events)) == CONFIG.open_floor_statements == 8


async def test_the_open_floor_ends_after_two_turns_in_which_nobody_bids() -> None:
    result = await play_game(CONFIG, puppets())

    assert open_floor(result.events) == []
    assert len(payloads(result.events, BidPlaced, day=1)) == 2 * CONFIG.residents


async def test_the_highest_bid_makes_the_next_statement() -> None:
    def seat_three_is_desperate(name: str, known: GameState) -> int:
        return 4 if seat_of(known)[name] == 3 else 1

    result = await play_game(CONFIG, puppets(bids=seat_three_is_desperate))

    speakers = {statement.speaker for statement in open_floor(result.events)}
    assert speakers == {name_at_seat(result.events, 3)}


async def test_a_tie_is_won_three_times_in_four_by_whoever_the_last_statement_addressed() -> None:
    def seats_one_and_two_tie(name: str, known: GameState) -> int:
        return 3 if seat_of(known)[name] in (1, 2) else 0

    def address_seat_one(request: DecisionRequest, known: GameState) -> Statement:
        return saying("Answer me, you!", addressed=[known.residents[1].name])

    wins = ties = 0
    for seed in range(300):
        config = CONFIG.model_copy(update={"seed": seed})
        result = await play_game(config, puppets(bids=seats_one_and_two_tie, says=address_seat_one))
        statements = payloads(result.events, StatementMade, day=1)
        opening_last = [s for s in statements if s.part == "opening_round"][-1]
        seat_one = name_at_seat(result.events, 1)
        if seat_one in opening_last.addressed:
            ties += 1
            wins += open_floor(result.events)[0].speaker == seat_one

    assert ties > 200
    assert 0.67 < wins / ties < 0.83


async def test_the_open_floor_stops_when_its_time_is_up() -> None:
    ticks = count(start=0, step=200)  # each look at the clock finds 200 more seconds gone
    config = CONFIG.model_copy(update={"open_floor_seconds": 300})

    result = await play_game(config, puppets(bids=keen), clock=lambda: next(ticks))

    assert len(open_floor(result.events)) == 1


async def test_each_bid_is_perceived_only_by_its_bidder() -> None:
    result = await play_game(CONFIG, puppets(bids=keen))

    for resident in result.state.residents:
        bids = payloads(perceived_by(result.events, resident.name), BidPlaced)
        assert bids
        assert {bid.resident for bid in bids} == {resident.name}


async def test_a_long_statement_is_cut_to_ninety_words() -> None:
    def rambles(request: DecisionRequest, known: GameState) -> Statement:
        return saying(" ".join(["blah"] * 150))

    result = await play_game(CONFIG, puppets(says=rambles))

    text = payloads(result.events, StatementMade)[0].text
    assert text.endswith("...")
    assert len(text.removesuffix("...").split()) == 90


async def test_a_statement_records_only_real_residents_other_than_the_speaker() -> None:
    def names_everyone(request: DecisionRequest, known: GameState) -> Statement:
        others = [r.name for r in known.residents if r.name != request.resident]
        return saying("Listen.", addressed=["Nobody", request.resident, others[0], others[0]])

    result = await play_game(CONFIG, puppets(says=names_everyone))

    for statement in payloads(result.events, StatementMade):
        assert len(statement.addressed) == 1
        assert statement.addressed[0] != statement.speaker
        assert statement.addressed[0] in {r.name for r in result.state.residents}


async def test_a_game_where_everyone_stays_quiet_and_skips_still_ends() -> None:
    config = CONFIG.model_copy(update={"max_days": 10})

    result = await play_game(config, puppets())

    assert payloads(result.events, GameEnded)
    assert result.events[-1].day == 10
