"""Vote: sealed ballots, then a banishment if one Resident clearly beats SKIP."""

from typing import TYPE_CHECKING

from mm.engine import Phase
from mm.engine.decisions import Ballot, DecisionKind, DecisionRequest
from mm.engine.events import BallotCast, ResidentDied, VoteResolved
from mm.engine.vote import ballot_options, tally_ballots, target_of

if TYPE_CHECKING:
    from mm.orchestrator.game import Game


async def run_vote(game: "Game") -> None:
    await game.start_phase(Phase.VOTE)
    requests = [
        DecisionRequest(DecisionKind.BALLOT, voter, ballot_options(game.state, voter))
        for voter in game.state.living
    ]
    ballots = await game.decide_all(requests, Ballot)

    for ballot in ballots:
        cast = BallotCast(voter=ballot.request.resident, target=target_of(ballot.decision.choice))
        await game.append(cast, cause=ballot)
    outcome = tally_ballots(ballot.decision.choice for ballot in ballots)
    await game.append(
        VoteResolved(tally=outcome.tally, skips=outcome.skips, banished=outcome.banished)
    )

    if outcome.banished:
        role = game.state.roles[outcome.banished]
        await game.append(ResidentDied(resident=outcome.banished, cause="banished", role=role))
