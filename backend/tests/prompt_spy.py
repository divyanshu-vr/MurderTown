"""A spy that builds the real Agent prompt at every decision point of a scripted game.

Its reflections, Den messages and Conversation messages carry a sentinel unique
to its Resident, and
every ballot it casts is reported as a fallback with a sentinel reason, which
only Spectators may perceive. A prompt that ever shows another Resident's
reflection sentinel, a Den sentinel outside the Den, or any fallback sentinel,
has leaked. The narrator is spied on too: it decides like a Resident.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from random import Random

from mm.agents import Brain, BrainFactory, scripted_bots
from mm.agents.prompting import Prompt, build_prompt
from mm.engine import GameConfig, Resident, Role
from mm.engine.decisions import (
    Answer,
    ConversationMessage,
    DecisionKind,
    DecisionRequest,
    DenMessage,
    Reflection,
    Statement,
)
from mm.engine.events import Event, ResidentInvestigated, SheriffFired
from mm.engine.perception import assignment
from mm.engine.state import GameState
from mm.orchestrator import play_game

FALLBACK_SENTINEL = "FALLBACK-SECRET"
DEN_SENTINEL = "DEN-WHISPER"
CONVERSATION_SENTINEL = "DUSK-MURMUR"


def conversation_sentinel(day: int, speaker: str, partner: str) -> str:
    """Unique to one speaker in one Conversation: a Resident has at most one per Day per partner."""
    return f"{CONVERSATION_SENTINEL}-{day}-{speaker}-{partner}"


@dataclass(frozen=True)
class Shown:
    resident: str
    request: DecisionRequest
    prompt: Prompt
    revealed: frozenset[str]
    """Whose role the Resident had seen revealed when the prompt was built: the dead's,
    a Sheriff's who has fired in public, and, for the Detective, whoever they investigated."""
    role: Role | None
    """The Resident's own role; the narrator has none."""

    def text(self) -> str:
        return "\n".join((self.prompt.system, self.prompt.memory, self.prompt.task))


class Spy:
    def __init__(self, inner: Brain, shown: list[Shown], says: str | None = None) -> None:
        self.inner, self.shown, self.says = inner, shown, says

    async def decide(self, request: DecisionRequest, view: Sequence[Event]) -> Answer:
        me = request.resident
        prompt = build_prompt(request, view, Random(me))
        shooters = {e.payload.sheriff for e in view if isinstance(e.payload, SheriffFired)}
        found = {e.payload.target for e in view if isinstance(e.payload, ResidentInvestigated)}
        revealed = frozenset(GameState.fold(view).dead) | shooters | found
        assigned = assignment(view, me)
        role = assigned.role if assigned else None
        self.shown.append(Shown(me, request, prompt, revealed, role))
        match request.kind:
            case DecisionKind.REFLECTION:
                notes = Reflection(
                    journal_entry=f"SECRET-{me}-journal",
                    notebook=f"SECRET-{me}-notebook",
                    suspicions=[],
                )
                return Answer(notes)
            case DecisionKind.STATEMENT if self.says:
                return Answer(Statement.plain(self.says))
            case DecisionKind.DEN_MESSAGE:
                return Answer(DenMessage(text=f"{DEN_SENTINEL}-{me}", proposed_victim=None))
            case DecisionKind.CONVERSATION_MESSAGE:
                day, partner = GameState.fold(view).day, request.options[0]
                said = conversation_sentinel(day, me, partner)
                return Answer(ConversationMessage(text=said, end_conversation=False))
            case DecisionKind.BALLOT:
                ballot = await self.inner.decide(request, view)
                return Answer(ballot.decision, fallback_reason=f"{FALLBACK_SENTINEL}-{me}")
            case _:
                return await self.inner.decide(request, view)


async def spy_on(
    config: GameConfig, says: dict[int, str] | None = None, inner: BrainFactory | None = None
) -> tuple[list[Shown], list[Event]]:
    """Play a game, collecting every prompt. `says` scripts Statements by seat.

    The other decisions come from `inner`, scripted bots unless a test says otherwise.
    """
    shown: list[Shown] = []
    deciders = inner or scripted_bots(config.seed)

    def make(resident: Resident) -> Brain:
        return Spy(deciders(resident), shown, (says or {}).get(resident.seat))

    result = await play_game(config, make)
    return shown, result.events
