"""Seam 1: the Open floor. Bids, Rights of reply, who speaks, and the three limits that end it."""

from itertools import pairwise

import pytest

from mm.engine import GameConfig, Role
from mm.engine.decisions import DecisionRequest, Statement
from mm.engine.events import BidPlaced, Event, GameEnded, OpenFloorTimedOut, StatementMade
from mm.engine.perception import perceived_by
from mm.engine.state import GameState
from mm.orchestrator import GameControls, play_game
from tests.support import (
    BidRule,
    StatementRule,
    everyone_alive_on_day_two,
    keen,
    may_perceive,
    name_at_seat,
    payloads,
    puppets,
    seat_of,
    seats_by_role,
    state_before,
    ticking,
)

CONFIG = GameConfig(residents=8, murderers=2, max_days=2, seed=4, open_floor_seconds=None)
"""Two Days: the game opens with a Night, so Day 2 has its only Discussion."""

ALL_ALIVE = everyone_alive_on_day_two(CONFIG)


def open_floor(events: list[Event]) -> list[StatementMade]:
    return [s for s in payloads(events, StatementMade, day=2) if s.part == "open_floor"]


async def test_the_open_floor_stops_at_its_statement_cap() -> None:
    result = await play_game(CONFIG, puppets(bids=keen))

    assert len(open_floor(result.events)) == CONFIG.open_floor_statements == 8


async def test_the_open_floor_ends_after_two_turns_in_which_nobody_bids() -> None:
    result = await play_game(CONFIG, puppets())

    bidding_starts = state_before(result.events, lambda event: isinstance(event.payload, BidPlaced))
    assert open_floor(result.events) == []
    assert len(payloads(result.events, BidPlaced, day=2)) == 2 * len(bidding_starts.living)


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
    return [s for s in payloads(events, StatementMade, day=2) if s.part == "opening_round"][-1]


@pytest.mark.parametrize(
    ("bids", "addressed", "possible_speakers"),
    [
        pytest.param({0: 1, 1: 1, 2: 1, 3: 4}, None, {3}, id="the single highest bid speaks"),
        pytest.param({1: 2, 2: 3}, 1, {2}, id="a higher bid beats being addressed"),
        pytest.param({}, None, set(), id="nobody speaks when every bid is 0"),
    ],
)
async def test_who_makes_the_first_statement_on_the_open_floor(
    bids: dict[int, int], addressed: int | None, possible_speakers: set[int]
) -> None:
    says = addressing(addressed) if addressed is not None else None

    result = await play_game(CONFIG, puppets(bids=bidding(bids), says=says, **ALL_ALIVE))

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


def asking(seat: int, otherwise: int) -> StatementRule:
    """Every Statement asks the Resident in `seat` to answer; theirs asks the one in `otherwise`."""

    def say(request: DecisionRequest, known: GameState) -> Statement:
        mine = seat_of(known)[request.resident]
        asked = known.residents[otherwise if mine == seat else seat].name
        return Statement.plain("Answer me!", asked=asked)

    return say


def speakers(events: list[Event]) -> list[str]:
    return [statement.speaker for statement in open_floor(events)]


async def test_whoever_the_last_opening_statement_asks_answers_first() -> None:
    bids = bidding({1: 1, 2: 1, 3: 3, 4: 3})

    result = await play_game(CONFIG, puppets(bids=bids, says=asking(1, otherwise=2), **ALL_ALIVE))

    asked = last_opening_statement(result.events).asked
    assert asked in {name_at_seat(result.events, seat) for seat in (1, 2)}
    first = open_floor(result.events)[0]
    assert (first.speaker, first.answering) == (asked, True)


async def test_a_resident_asked_by_every_statement_answers_once_per_open_floor() -> None:
    bids = bidding({1: 1, 2: 1, 3: 3, 4: 3})

    result = await play_game(CONFIG, puppets(bids=bids, says=asking(1, otherwise=2), **ALL_ALIVE))

    assert speakers(result.events).count(name_at_seat(result.events, 1)) == 1


async def test_a_resident_asked_to_answer_may_decline_by_bidding_nothing() -> None:
    bids = bidding({3: 2, 4: 2})

    result = await play_game(CONFIG, puppets(bids=bids, says=asking(1, otherwise=2), **ALL_ALIVE))

    spoke = speakers(result.events)
    assert spoke
    assert not {name_at_seat(result.events, seat) for seat in (1, 2)} & set(spoke)


async def test_equal_bids_take_turns_by_who_has_waited_longest() -> None:
    result = await play_game(CONFIG, puppets(bids=bidding({1: 3, 2: 3}), **ALL_ALIVE))

    one, two = (name_at_seat(result.events, seat) for seat in (1, 2))
    opening = [s.speaker for s in payloads(result.events, StatementMade, day=2)][:8]
    first, second = sorted((one, two), key=opening.index)
    assert speakers(result.events) == [first, second] * 4


async def test_two_residents_addressing_each_other_soon_give_way_to_others() -> None:
    def at_each_other(request: DecisionRequest, known: GameState) -> Statement:
        other = 2 if seat_of(known)[request.resident] == 1 else 1
        return Statement.plain("You again!", addressed=[known.residents[other].name])

    bids = bidding({1: 4, 2: 4, 3: 3})

    result = await play_game(CONFIG, puppets(bids=bids, says=at_each_other, **ALL_ALIVE))

    assert name_at_seat(result.events, 3) in speakers(result.events)[:3]


async def test_a_keen_bidder_still_gets_the_floor_when_every_statement_asks_someone() -> None:
    def ask_the_next(request: DecisionRequest, known: GameState) -> Statement:
        names = [resident.name for resident in known.residents]
        asked = names[(names.index(request.resident) + 1) % len(names)]
        return Statement.plain("Your turn to explain.", asked=asked)

    keen_one = bidding({seat: 1 for seat in range(8)} | {3: 3})

    result = await play_game(CONFIG, puppets(bids=keen_one, says=ask_the_next, **ALL_ALIVE))

    statements = open_floor(result.events)
    assert speakers(result.events).count(name_at_seat(result.events, 3)) >= 3
    assert sum(statement.answering for statement in statements) >= 2  # questions still answered


async def test_a_statement_asks_only_a_living_resident() -> None:
    roles = seats_by_role(CONFIG)
    victim, spared = roles[Role.CIVILIAN][:2]

    def ask_the_dead(request: DecisionRequest, known: GameState) -> Statement:
        return Statement.plain("Speak up!", asked=known.residents[victim].name)

    nights = {"kills": {1: victim}, "protects": {1: spared}}
    result = await play_game(CONFIG, puppets(says=ask_the_dead, **nights))

    statements = payloads(result.events, StatementMade, day=2)
    assert statements
    assert all(statement.asked is None for statement in statements)


async def test_the_open_floor_stops_when_its_time_is_up_and_everyone_hears_so() -> None:
    config = CONFIG.model_copy(update={"open_floor_seconds": 300})

    result = await play_game(config, puppets(bids=keen), controls=GameControls(clock=ticking(200)))

    assert len(open_floor(result.events)) == 1
    timed_out = next(e for e in result.events if isinstance(e.payload, OpenFloorTimedOut))
    assert all(may_perceive(timed_out, r.name) for r in result.state.residents)


async def test_each_statement_on_a_timed_open_floor_records_the_time_it_has_left() -> None:
    config = CONFIG.model_copy(update={"open_floor_seconds": 300})

    result = await play_game(config, puppets(bids=keen), controls=GameControls(clock=ticking(10)))

    day_two = payloads(result.events, StatementMade, day=2)
    opening = [said for said in day_two if said.part == "opening_round"]
    left = [
        said.seconds_left for said in day_two if said.part == "open_floor" and said.seconds_left
    ]
    assert all(said.seconds_left is None for said in opening)
    assert len(left) == 8
    assert all(0 < seconds < 300 for seconds in left)
    assert all(earlier > later for earlier, later in pairwise(left))


async def test_a_statement_on_an_open_floor_without_a_time_limit_records_no_time() -> None:
    result = await play_game(CONFIG, puppets(bids=keen))

    assert all(statement.seconds_left is None for statement in open_floor(result.events))


async def test_each_bid_is_perceived_only_by_its_bidder() -> None:
    result = await play_game(CONFIG, puppets(bids=keen, **ALL_ALIVE))

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
