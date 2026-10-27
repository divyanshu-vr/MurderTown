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
    voters = game.state.living
    requests = [
        DecisionRequest(DecisionKind.BALLOT, voter, ballot_options(game.state, voter))
        for voter in voters
    ]
    ballots = await game.decide_all(requests, Ballot)

    for voter, ballot in zip(voters, ballots, strict=True):
        await game.append(BallotCast(voter=voter, target=target_of(ballot.choice)))
    outcome = tally_ballots(ballot.choice for ballot in ballots)
    await game.append(
        VoteResolved(tally=outcome.tally, skips=outcome.skips, banished=outcome.banished)
    )

    if outcome.banished:
        role = game.state.roles[outcome.banished]
        await game.append(ResidentDied(resident=outcome.banished, cause="banished", role=role))
