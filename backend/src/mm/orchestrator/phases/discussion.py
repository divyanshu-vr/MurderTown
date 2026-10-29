"""Discussion: the public debate in the town square.

The Opening round comes first: every living Resident makes exactly one
Statement, in a random order that changes every Day. Then the Open floor: each
Turn, every living Resident bids and the engine's `Floor` says who speaks (a Right
of reply, then the highest Bid, then whoever waited longest). The Open floor ends at its
Statement cap, its time limit, or after two quiet Turns in a row.
"""

from typing import TYPE_CHECKING

from mm.engine import Phase
from mm.engine.decisions import Bid, DecisionKind, DecisionRequest, Statement, StatementPart
from mm.engine.discussion import Floor, addressing, open_floor_limit
from mm.engine.events import BidPlaced, OpenFloorTimedOut, StatementMade
from mm.engine.rules import named, trimmed

if TYPE_CHECKING:
    from mm.orchestrator.game import Game


async def run_discussion(game: "Game") -> None:
    await game.start_phase(Phase.DISCUSSION)
    order = list(game.state.living)
    game.rng.shuffle(order)
    floor = Floor()
    for speaker in order:
        floor = floor.after(await _statement(game, speaker, "opening_round"))
    await _open_floor(game, floor)


async def _open_floor(game: "Game", floor: Floor) -> None:
    """Turns until a limit is reached. Running out of time is recorded, so a replay of the
    game, whose clock reads differently, runs out at the same point."""
    started = game.clock()
    statements_made = quiet_turns = 0
    while True:
        out_of_time = game.open_floor_out_of_time(started)
        if limit := open_floor_limit(game.config, statements_made, quiet_turns, out_of_time):
            if limit == "time":
                await game.append(OpenFloorTimedOut())
            return
        requests = [DecisionRequest(DecisionKind.BID, name) for name in game.state.living]
        bids = await game.decide_all(requests, Bid)
        for bid in bids:
            placed = BidPlaced(
                resident=bid.request.resident,
                urgency=bid.decision.urgency,
                reason=bid.decision.reason,
            )
            await game.append(placed, cause=bid)

        urgency = {bid.request.resident: bid.decision.urgency for bid in bids}
        speaker = floor.next_speaker(urgency)
        if speaker is None:
            quiet_turns += 1
            continue
        quiet_turns = 0
        answering = floor.answers(speaker, urgency[speaker])
        floor = floor.after(await _statement(game, speaker, "open_floor", answering))
        statements_made += 1


async def _statement(
    game: "Game", speaker: str, part: StatementPart, answering: bool = False
) -> StatementMade:
    request = DecisionRequest(DecisionKind.STATEMENT, speaker, part=part)
    said = await game.decide(request, Statement)
    statement = said.decision
    others = [resident.name for resident in game.state.residents if resident.name != speaker]
    addressed, asked = addressing(
        statement.addressed, statement.asked, others, game.state.others_living(speaker)
    )
    made = StatementMade(
        speaker=speaker,
        text=trimmed(statement.text),
        part=part,
        addressed=addressed,
        asked=asked,
        answering=answering,
        accused=named(statement.accused, others),
        defended=named(statement.defended, others),
        claimed_role=statement.claimed_role,
    )
    await game.append(made, cause=said)
    return made
