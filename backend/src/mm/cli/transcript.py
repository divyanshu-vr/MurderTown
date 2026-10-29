"""A readable, Spectator's-eye transcript of a game, for the terminal.

The console only needs plain ASCII, so the transcript avoids box-drawing
characters that some Windows terminals cannot print.
"""

from typing import assert_never

from mm.agents.prompting import ACTIVITIES
from mm.engine import Side, events
from mm.engine.events import Event

SIDES = {Side.TOWN: "Town", Side.MURDERERS: "Murderers"}

VICTORY = {Side.TOWN: "The Town wins.", Side.MURDERERS: "The Murderers win."}

DEATHS = {
    "banished": "leaves the town forever",
    "shot": "falls to the Sheriff's bullet",
    "backfire": "is struck down by the backfire",
    "murdered": "is found murdered",
}


def describe(event: Event) -> str | None:  # noqa: C901, PLR0912 - one case per event type
    """One readable line per event, or None for events not worth printing (quiet bids).

    Every event type has a case, so a new one cannot be forgotten.
    """
    match event.payload:
        case events.GameConfigured():
            return None  # the opening line names the Residents; the roles follow
        case events.GameStarted(residents=residents):
            names = ", ".join(f"{r.name} the {r.occupation}" for r in residents)
            return f"{len(residents)} Residents move into town: {names}."
        case events.RoleAssigned(resident=resident, role=role, teammates=teammates):
            partners = f" (with {', '.join(teammates)})" if teammates else ""
            return f"  {resident} is secretly a {role.capitalize()}{partners}."
        case events.PhaseStarted(day=day, phase=phase):
            return f"\n=== Day {day}: {phase.capitalize()} ==="
        case events.BidPlaced(resident=resident, urgency=urgency, reason=reason):
            return f"  ({resident} bids {urgency}: {reason})" if urgency else None
        case events.StatementMade(speaker=speaker, text=text):
            return f'{speaker}: "{text}"'
        case events.OpenFloorTimedOut():
            return "  (Time is up on the Open floor.)"
        case events.SheriffFired(sheriff=sheriff, target=target):
            return f"BANG! {sheriff}, the Sheriff, fires at {target}."
        case events.SheriffHeldFire(sheriff=sheriff):
            return f"  ({sheriff}, the Sheriff, holds fire.)"
        case events.LastWordsSpoken(resident=resident, text=text):
            return f'{resident}\'s last words: "{text}"'
        case events.BallotCast(voter=voter, target=target):
            return f"  {voter} votes for {target}" if target else f"  {voter} votes to skip"
        case events.VoteResolved(tally=tally, skips=skips, banished=banished):
            counts = [f"{name} {votes}" for name, votes in tally.items()] + [f"skip {skips}"]
            result = f"{banished} is banished." if banished else "Nobody is banished."
            return f"Tally: {', '.join(counts)}. {result}"
        case events.ResidentDied(resident=resident, cause=cause, role=role):
            return f"{resident} {DEATHS[cause]}. They were a {role.capitalize()}."
        case events.DenMessagePosted(murderer=murderer, text=text, proposed_victim=proposal):
            proposed = f" (proposes {proposal})" if proposal else ""
            return f'  [Den] {murderer}: "{text}"{proposed}'
        case events.KillVoteCast(murderer=murderer, target=target):
            return f"  [Den] {murderer} votes to kill {target}."
        case events.VictimChosen(victim=victim):
            return f"  [Den] The Murderers choose {victim}."
        case events.ResidentProtected(doctor=doctor, target=target):
            return f"  ({doctor}, the Doctor, protects {target}.)"
        case events.ResidentInvestigated(detective=detective, target=target, found_murderer=found):
            finding = "a Murderer" if found else "not a Murderer"
            return f"  ({detective}, the Detective, learns that {target} is {finding}.)"
        case events.AttackThwarted(saved=saved):
            return f"{saved or 'Someone'} was attacked in the night, but the Doctor saved them."
        case events.RecapNarrated(text=text):
            return f"Narrator: {text}"
        case events.DuskIntentChosen(resident=resident, activity="talk", partners=partners):
            return f"  ({resident} hopes to talk with {', '.join(partners)}.)"
        case events.DuskIntentChosen(resident=resident, activity=activity):
            return f"  ({resident} means to {ACTIVITIES[activity]}.)"
        case events.ConversationStarted(residents=(one, other)):
            return f"[Dusk] {one} and {other} slip away to talk."
        case events.ConversationMessagePosted(speaker=speaker, partner=partner, text=text):
            return f'  [Dusk] {speaker} to {partner}: "{text}"'
        case events.ReflectionWritten(resident=resident, journal_entry=entry):
            return f"  ({resident} writes privately: {entry})"
        case events.DecisionFellBack(resident=resident, kind=kind, reason=reason):
            return f"  [fallback] {resident}'s {kind} used a safe default: {reason}"
        case events.RolesRevealed():
            return "\nEvery role is revealed."
        case events.GameEnded(winner=winner, reason=reason):
            return f"\n*** {VICTORY[winner]} {reason} ***"
        case events.DecisionUnanswered(resident=resident, kind=kind, reason=reason):
            return f"  [no answer] {resident}'s {kind} got no answer: {reason}"
        case events.GameAborted(reason=reason):
            return f"\n*** The game is aborted: {reason} ***"
        case unknown:
            assert_never(unknown)
