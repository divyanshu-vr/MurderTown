"""Everything that happens in a game is an event in one append-only log.

Each event type declares who may perceive it (its visibility) right next to its
definition, so the rule for who knows what lives in exactly one place. An
Agent's knowledge is built only from the events it may perceive.
"""

from collections.abc import Iterable
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

from mm.engine.config import GameConfig, Rules
from mm.engine.decisions import DecisionKind, DuskActivity, StatementPart, Suspicion
from mm.engine.personas import Persona
from mm.engine.phases import Phase
from mm.engine.residents import Resident
from mm.engine.roles import Role, Side

PROTOCOL = ConfigDict(frozen=True, json_schema_serialization_defaults_required=True)
"""Shared by everything sent to the frontend: immutable, and every field always present."""


class Visibility(BaseModel):
    """Who may perceive an event: everyone, a named set of Residents, or no Resident at all
    (`spectators`). Public scope shows only what everyone perceives; full scope shows it all."""

    model_config = PROTOCOL

    scope: Literal["everyone", "residents", "spectators"]
    residents: tuple[str, ...] = ()

    @classmethod
    def everyone(cls) -> "Visibility":
        return cls(scope="everyone")

    @classmethod
    def only(cls, *residents: str) -> "Visibility":
        return cls(scope="residents", residents=residents)

    @classmethod
    def spectators(cls) -> "Visibility":
        return cls(scope="spectators")

    def allows(self, resident: str) -> bool:
        return self.scope == "everyone" or resident in self.residents

    @property
    def public(self) -> bool:
        """Whether the whole town perceives it: all that public scope is sent."""
        return self.scope == "everyone"


class Payload(BaseModel):
    """Base for every event payload. Each subclass must say who may perceive it."""

    model_config = ConfigDict(**PROTOCOL, extra="forbid")

    def visibility(self) -> Visibility:
        raise NotImplementedError(f"{type(self).__name__} must declare its visibility")


class GameConfigured(Payload):
    """Everything the Host chose, seed and lineup included. No Resident perceives it, so only
    full scope shows it: casting follows from the seed, so knowing it would tell every role."""

    type: Literal["game_configured"] = "game_configured"
    config: GameConfig

    def visibility(self) -> Visibility:
        return Visibility.spectators()


class GameStarted(Payload):
    """Who lives in the town, and the rules everyone plays by."""

    type: Literal["game_started"] = "game_started"
    rules: Rules
    residents: tuple[Resident, ...]

    def visibility(self) -> Visibility:
        return Visibility.everyone()


class RoleAssigned(Payload):
    """A Resident learns their role and persona. Murderers also learn who their teammates are."""

    type: Literal["role_assigned"] = "role_assigned"
    resident: str
    role: Role
    persona: Persona
    teammates: tuple[str, ...] = ()

    def visibility(self) -> Visibility:
        return Visibility.only(self.resident)


class PhaseStarted(Payload):
    type: Literal["phase_started"] = "phase_started"
    day: int
    phase: Phase

    def visibility(self) -> Visibility:
        return Visibility.everyone()


class BidPlaced(Payload):
    """How urgently one Resident wants to make the next Statement on the Open floor."""

    type: Literal["bid_placed"] = "bid_placed"
    resident: str
    urgency: int
    reason: str

    def visibility(self) -> Visibility:
        return Visibility.only(self.resident)


class StatementMade(Payload):
    """A Statement, with what it does: whom it names, accuses and defends, and any role claim.
    `asked` is the living Resident it asks to answer next, also among those it addresses.
    `answering` says its speaker took the Open floor to answer, by Right of reply or a 4
    that counted, so it starts no answer of its own."""

    type: Literal["statement_made"] = "statement_made"
    speaker: str
    text: str
    part: StatementPart
    addressed: tuple[str, ...] = ()
    asked: str | None = None
    answering: bool = False
    accused: tuple[str, ...] = ()
    defended: tuple[str, ...] = ()
    claimed_role: Role | None = None

    def visibility(self) -> Visibility:
        return Visibility.everyone()


class OpenFloorTimedOut(Payload):
    """The Open floor's time limit ended it, before its Statement cap or two quiet Turns.

    Recorded because it depends on the clock: a resumed game replays the record.
    """

    type: Literal["open_floor_timed_out"] = "open_floor_timed_out"

    def visibility(self) -> Visibility:
        return Visibility.everyone()


class SheriffFired(Payload):
    """The Sheriff spends the single bullet. Whoever is hit, and perhaps the Sheriff, dies next."""

    type: Literal["sheriff_fired"] = "sheriff_fired"
    sheriff: str
    target: str
    hit_a_murderer: bool

    def visibility(self) -> Visibility:
        return Visibility.everyone()


class SheriffHeldFire(Payload):
    """The Sheriff chose not to fire this time and keeps the bullet.

    It is recorded so every decision leaves a mark in the log. Only Spectators
    perceive it: the town learns nothing, and the Sheriff already knows.
    """

    type: Literal["sheriff_held_fire"] = "sheriff_held_fire"
    sheriff: str

    def visibility(self) -> Visibility:
        return Visibility.spectators()


class BallotCast(Payload):
    """One Resident's ballot, revealed once every ballot of the Vote has been cast."""

    type: Literal["ballot_cast"] = "ballot_cast"
    voter: str
    target: str | None
    """The Resident voted for, or None for a vote to skip."""

    def visibility(self) -> Visibility:
        return Visibility.everyone()


class VoteResolved(Payload):
    type: Literal["vote_resolved"] = "vote_resolved"
    tally: dict[str, int]
    """Ballots against each Resident who received any."""
    skips: int
    banished: str | None

    def visibility(self) -> Visibility:
        return Visibility.everyone()


class LastWordsSpoken(Payload):
    """What a banished Resident says before their role is revealed."""

    type: Literal["last_words_spoken"] = "last_words_spoken"
    resident: str
    text: str

    def visibility(self) -> Visibility:
        return Visibility.everyone()


class DenPayload(Payload):
    """Something that happens in the Den: only the Murderers alive that Night perceive it."""

    den: tuple[str, ...]
    """The living Murderers, who alone perceive it."""

    def visibility(self) -> Visibility:
        return Visibility.only(*self.den)


class DenMessagePosted(DenPayload):
    """One Murderer's message to the others, perhaps proposing tonight's Victim."""

    type: Literal["den_message_posted"] = "den_message_posted"
    murderer: str
    text: str
    proposed_victim: str | None


class KillVoteCast(DenPayload):
    """One Murderer's choice of Victim; a lone Murderer's choice settles it."""

    type: Literal["kill_vote_cast"] = "kill_vote_cast"
    murderer: str
    target: str


class VictimChosen(DenPayload):
    """The Den's Victim: the most kill votes, with a tie drawn at random."""

    type: Literal["victim_chosen"] = "victim_chosen"
    victim: str


class ResidentProtected(Payload):
    """The Doctor's protection for the Night. If the Murderers attack this Resident, they live."""

    type: Literal["resident_protected"] = "resident_protected"
    doctor: str
    target: str

    def visibility(self) -> Visibility:
        return Visibility.only(self.doctor)


class ResidentInvestigated(Payload):
    """What the Detective learns about one Resident. It is not always right."""

    type: Literal["resident_investigated"] = "resident_investigated"
    detective: str
    target: str
    found_murderer: bool

    def visibility(self) -> Visibility:
        return Visibility.only(self.detective)


class AttackThwarted(Payload):
    """Dawn's news that the Murderers attacked someone the Doctor had protected."""

    type: Literal["attack_thwarted"] = "attack_thwarted"
    saved: str | None
    """Who was saved, or None when the game is set up not to say."""

    def visibility(self) -> Visibility:
        return Visibility.everyone()


class DuskIntentChosen(Payload):
    """What a Resident means to do at Dusk: talk, wander or do a chore. Only they know."""

    type: Literal["dusk_intent_chosen"] = "dusk_intent_chosen"
    resident: str
    activity: DuskActivity
    partners: tuple[str, ...]
    topic: str

    def visibility(self) -> Visibility:
        return Visibility.only(self.resident)


class ConversationStarted(Payload):
    """Two Residents slip away to talk. Everyone sees that they met, but not who asked whom."""

    type: Literal["conversation_started"] = "conversation_started"
    residents: tuple[str, str]
    """The two Residents, in seat order."""

    def visibility(self) -> Visibility:
        return Visibility.everyone()


class ConversationMessagePosted(Payload):
    """One message in a Conversation, heard only by the two Residents in it."""

    type: Literal["conversation_message_posted"] = "conversation_message_posted"
    speaker: str
    partner: str
    text: str
    ends_conversation: bool

    def visibility(self) -> Visibility:
        return Visibility.only(self.speaker, self.partner)


class RecapNarrated(Payload):
    """The narrator's short recap of the Day so far, told at Dawn."""

    type: Literal["recap_narrated"] = "recap_narrated"
    text: str

    def visibility(self) -> Visibility:
        return Visibility.everyone()


class ResidentDied(Payload):
    """A death, announced to everyone with the dead Resident's role.

    A Resident is banished by Vote, shot by the Sheriff or murdered at Night; a
    Sheriff who shoots a Town Resident dies of the backfire.
    """

    type: Literal["resident_died"] = "resident_died"
    resident: str
    cause: Literal["banished", "shot", "backfire", "murdered"]
    role: Role

    def visibility(self) -> Visibility:
        return Visibility.everyone()


class ReflectionWritten(Payload):
    """A Resident's private journal entry, rewritten notebook and changed suspicions."""

    type: Literal["reflection_written"] = "reflection_written"
    resident: str
    journal_entry: str
    notebook: str
    suspicions: tuple[Suspicion, ...]

    def visibility(self) -> Visibility:
        return Visibility.only(self.resident)


class DecisionFellBack(Payload):
    """A decision source could not give a usable answer, so a safe default was used instead."""

    type: Literal["decision_fell_back"] = "decision_fell_back"
    resident: str
    kind: DecisionKind
    reason: str

    def visibility(self) -> Visibility:
        return Visibility.spectators()


class RolesRevealed(Payload):
    """As a side wins, every role becomes public, so the story ends for every Spectator and
    for the town. Only the roles: the Den, the Night actions and private Conversations stay
    as hidden as they were."""

    type: Literal["roles_revealed"] = "roles_revealed"
    roles: dict[str, Role]
    """Every Resident's role, by name, in seat order."""

    def visibility(self) -> Visibility:
        return Visibility.everyone()


class GameEnded(Payload):
    type: Literal["game_ended"] = "game_ended"
    winner: Side
    reason: str

    def visibility(self) -> Visibility:
        return Visibility.everyone()


class DecisionUnanswered(Payload):
    """The model gave no answer at all to a decision, so the game is aborted right after. No
    Resident perceives it, so only full scope shows it: whose decision it was, and of what
    kind, could reveal a Night role."""

    type: Literal["decision_unanswered"] = "decision_unanswered"
    resident: str
    kind: DecisionKind
    reason: str

    def visibility(self) -> Visibility:
        return Visibility.spectators()


class GameAborted(Payload):
    """The game stopped before either side won: a decision got no answer, or the game itself
    failed. `reason` is only the problem, such as a timeout, never the decision itself, so the
    whole town may see the game stop."""

    type: Literal["game_aborted"] = "game_aborted"
    reason: str

    def visibility(self) -> Visibility:
        return Visibility.everyone()


EventPayload = Annotated[
    GameConfigured
    | GameStarted
    | RoleAssigned
    | PhaseStarted
    | BidPlaced
    | StatementMade
    | OpenFloorTimedOut
    | SheriffFired
    | SheriffHeldFire
    | BallotCast
    | VoteResolved
    | LastWordsSpoken
    | ResidentDied
    | DenMessagePosted
    | KillVoteCast
    | VictimChosen
    | ResidentProtected
    | ResidentInvestigated
    | AttackThwarted
    | RecapNarrated
    | DuskIntentChosen
    | ConversationStarted
    | ConversationMessagePosted
    | ReflectionWritten
    | DecisionFellBack
    | RolesRevealed
    | GameEnded
    | DecisionUnanswered
    | GameAborted,
    Field(discriminator="type"),
]


def ends_the_game(payload: Payload) -> bool:
    """Whether nothing can follow this event: a side won, or the game was aborted."""
    return isinstance(payload, GameEnded | GameAborted)


class Event(BaseModel):
    """One entry in a game's log: a payload stamped with its place in the game."""

    model_config = PROTOCOL

    seq: int
    day: int
    phase: Phase
    visibility: Visibility
    decision_id: str | None = None
    """The decision that caused this event, if any."""
    payload: EventPayload


def payloads_of[P: Payload](events: Iterable[Event], kind: type[P]) -> list[P]:
    """Every payload of one type, in the order logged."""
    return [event.payload for event in events if isinstance(event.payload, kind)]
