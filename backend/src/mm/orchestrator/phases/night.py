"""Night: the town sleeps while the Murderers choose a Victim and the Doctor and Detective act.

In order: the Sheriff's shot, if the game is set up for it at Night, from Night 2
on, once the town has had a Day to talk (the opening Night gives nothing to go
on); then, if
more than one Murderer is alive, each posts one message in the Den, one after
another so each hears the last; then every kill vote, the Doctor's protection
and the Detective's investigation are asked for at once. Their events follow in
a fixed order, so the log is the same however fast each answer comes. Dawn
reveals what came of it.
"""

from typing import TYPE_CHECKING

from mm.engine import Phase, Role
from mm.engine.decisions import DecisionKind, DecisionRequest, DenMessage, Target
from mm.engine.events import (
    DenMessagePosted,
    KillVoteCast,
    ResidentInvestigated,
    ResidentProtected,
    VictimChosen,
)
from mm.engine.night import (
    den_proposal,
    investigate_options,
    investigation_finding,
    kill_options,
    protect_options,
)
from mm.engine.rules import trimmed
from mm.engine.showdown import armed_sheriff
from mm.engine.tally import plurality
from mm.orchestrator.phases.showdown import sheriff_decides

if TYPE_CHECKING:
    from mm.orchestrator.game import Decided, Game


async def run_night(game: "Game") -> None:
    await game.start_phase(Phase.NIGHT)
    shoots_tonight = game.config.sheriff_shoots_at == "night" and game.state.day > 1
    if shoots_tonight and (sheriff := armed_sheriff(game.state)):
        await sheriff_decides(game, sheriff)
        if game.decided:
            return

    murderers = tuple(game.state.living_as(Role.MURDERER))
    if len(murderers) > 1:
        await _den(game, murderers)

    choices = await game.decide_all(_night_requests(game), Target)
    by_kind = {kind: [c for c in choices if c.request.kind is kind] for kind in DecisionKind}
    await _kill(game, murderers, by_kind[DecisionKind.KILL_VOTE])
    for protection in by_kind[DecisionKind.PROTECT]:
        doctor, target = protection.request.resident, protection.decision.target
        await game.append(ResidentProtected(doctor=doctor, target=target), cause=protection)
    for investigation in by_kind[DecisionKind.INVESTIGATE]:
        await _investigate(game, investigation)


async def _den(game: "Game", murderers: tuple[str, ...]) -> None:
    """Each Murderer in turn says one thing to the others, perhaps proposing a Victim."""
    for murderer in murderers:
        options = kill_options(game.state)
        request = DecisionRequest(DecisionKind.DEN_MESSAGE, murderer, options)
        said = await game.decide(request, DenMessage)
        posted = DenMessagePosted(
            murderer=murderer,
            text=trimmed(said.decision.text),
            proposed_victim=den_proposal(said.decision.proposed_victim, options),
            den=murderers,
        )
        await game.append(posted, cause=said)


def _night_requests(game: "Game") -> list[DecisionRequest]:
    """Every Night choice to ask for at once. A role with no one left to choose is not asked."""
    state = game.state
    requests = [
        DecisionRequest(DecisionKind.KILL_VOTE, murderer, kill_options(state))
        for murderer in state.living_as(Role.MURDERER)
    ]
    requests += [
        DecisionRequest(DecisionKind.PROTECT, doctor, protect_options(state, doctor))
        for doctor in state.living_as(Role.DOCTOR)
    ]
    requests += [
        DecisionRequest(DecisionKind.INVESTIGATE, detective, investigate_options(state, detective))
        for detective in state.living_as(Role.DETECTIVE)
    ]
    return [request for request in requests if request.options]


async def _kill(game: "Game", murderers: tuple[str, ...], votes: list["Decided[Target]"]) -> None:
    for vote in votes:
        murderer, target = vote.request.resident, vote.decision.target
        await game.append(KillVoteCast(murderer=murderer, target=target, den=murderers), cause=vote)
    if votes:
        victim = plurality((vote.decision.target for vote in votes), game.rng)
        await game.append(VictimChosen(victim=victim, den=murderers))


async def _investigate(game: "Game", investigation: "Decided[Target]") -> None:
    target = investigation.decision.target
    found = investigation_finding(
        game.state.roles[target] is Role.MURDERER, game.config.detective_accuracy, game.rng
    )
    investigated = ResidentInvestigated(
        detective=investigation.request.resident, target=target, found_murderer=found
    )
    await game.append(investigated, cause=investigation)
