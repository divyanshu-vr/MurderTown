"""A spy that builds the real Agent prompt at every decision point of a scripted game.

Its reflections carry a sentinel unique to its Resident, and every ballot it
casts is reported as a fallback with a sentinel reason, which only Spectators
may perceive. A prompt that ever shows another Resident's sentinel, or any
fallback sentinel, has leaked.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from random import Random

from mm.agents import Brain, BrainFactory, scripted_bots
from mm.agents.prompting import Prompt, build_prompt
from mm.engine import GameConfig, Resident, Role
from mm.engine.decisions import Answer, DecisionKind, DecisionRequest, Reflection, Statement
from mm.engine.events import Event, SheriffFired
from mm.engine.perception import briefing
from mm.engine.state import GameState
from mm.orchestrator import play_game

FALLBACK_SENTINEL = "FALLBACK-SECRET"


@dataclass(frozen=True)
class Shown:
    resident: str
    request: DecisionRequest
    prompt: Prompt
    revealed: frozenset[str]
    """Whose role the Resident had seen revealed when the prompt was built: the dead's,
    and a Sheriff's who has fired in public."""
    role: Role
    """The Resident's own role."""

    def text(self) -> str:
        return self.prompt.system + "\n" + self.prompt.user_message()


class Spy:
    def __init__(self, inner: Brain, shown: list[Shown], says: str | None = None) -> None:
        self.inner, self.shown, self.says = inner, shown, says

    async def decide(self, request: DecisionRequest, view: Sequence[Event]) -> Answer:
        me = request.resident
        prompt = build_prompt(request, view, Random(me))
        shooters = {e.payload.sheriff for e in view if isinstance(e.payload, SheriffFired)}
        revealed = frozenset(GameState.fold(view).dead) | shooters
        self.shown.append(Shown(me, request, prompt, revealed, briefing(view, me).role))
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
