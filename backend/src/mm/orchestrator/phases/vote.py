"""Vote: sealed ballots, a banishment if one Resident clearly beats SKIP, then reflection.

A banished Resident says their last words before their role is revealed.
"""

from typing import TYPE_CHECKING

from mm.engine import Phase
from mm.engine.decisions import DecisionKind, DecisionRequest, LastWords, Target
from mm.engine.events import BallotCast, LastWordsSpoken, ResidentDied, VoteResolved
from mm.engine.rules import trimmed
from mm.engine.vote import ballot_options, tally_ballots, target_of
from mm.orchestrator.phases.reflection import reflect

if TYPE_CHECKING:
    from mm.orchestrator.game import Game


async def run_vote(game: "Game") -> None:
    await game.start_phase(Phase.VOTE)
    requests = [
        DecisionRequest(DecisionKind.BALLOT, voter, ballot_options(game.state, voter))
        for voter in game.state.living
    ]
    ballots = await game.decide_all(requests, Target)

    for ballot in ballots:
        cast = BallotCast(voter=ballot.request.resident, target=target_of(ballot.decision.target))
        await game.append(cast, cause=ballot)
    outcome = tally_ballots(ballot.decision.target for ballot in ballots)
    await game.append(
        VoteResolved(tally=outcome.tally, skips=outcome.skips, banished=outcome.banished)
    )

    if banished := outcome.banished:
        words = await game.decide(DecisionRequest(DecisionKind.LAST_WORDS, banished), LastWords)
        spoken = LastWordsSpoken(resident=banished, text=trimmed(words.decision.text))
        await game.append(spoken, cause=words)
        role = game.state.roles[banished]
        await game.append(ResidentDied(resident=banished, cause="banished", role=role))
    await reflect(game)
