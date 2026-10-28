"""An Agent's memory, folded from its own reflections. There is no separate memory store.

Each reflection rewrites the notebook in full, adds a journal entry and updates
the dossier. Prompts show the newest notebook, the dossier and only the last few
journal entries, so the amount of text stays the same however long the game runs.

The Mind inspector's server view, `mind_of`, is the same fold behind the same
perception door, so it shows exactly what the Agent had in mind.
"""

from collections.abc import Sequence

from pydantic import BaseModel

from mm.engine import Role
from mm.engine.decisions import Suspicion
from mm.engine.events import PROTOCOL, Event, ReflectionWritten
from mm.engine.perception import assignment, perceived_by
from mm.engine.personas import Persona
from mm.engine.phases import Phase


class JournalEntry(BaseModel):
    model_config = PROTOCOL

    day: int
    phase: Phase
    text: str


class Memory(BaseModel):
    """What a Resident carries in mind from one decision to the next."""

    model_config = PROTOCOL

    notebook: str
    journal: tuple[JournalEntry, ...]
    """Every entry, oldest first."""
    dossier: tuple[Suspicion, ...]
    """The latest suspicion about each other Resident they have rated, sorted by name."""


def remember(view: Sequence[Event], resident: str) -> Memory:
    """Fold a Resident's own reflections.

    A reflection with an empty notebook (a fallback, say) keeps the previous
    notebook, empty journal entries are skipped, and the latest suspicion about
    each Resident replaces any earlier one.
    """
    notebook = ""
    journal: list[JournalEntry] = []
    dossier: dict[str, Suspicion] = {}
    for event in view:
        reflection = event.payload
        if not isinstance(reflection, ReflectionWritten) or reflection.resident != resident:
            continue
        notebook = reflection.notebook or notebook
        if text := reflection.journal_entry:
            journal.append(JournalEntry(day=event.day, phase=event.phase, text=text))
        dossier.update({s.resident: s for s in reflection.suspicions})
    return Memory(
        notebook=notebook,
        journal=tuple(journal),
        dossier=tuple(suspicion for _, suspicion in sorted(dossier.items())),
    )


class Mind(BaseModel):
    """One Resident's mind at one moment: who they are, what they remember, what they perceived."""

    model_config = PROTOCOL

    resident: str
    role: Role
    persona: Persona
    teammates: tuple[str, ...]
    memory: Memory
    perceived: tuple[Event, ...]


def mind_of(events: Sequence[Event], resident: str) -> Mind | None:
    """A Resident's mind once `events` have happened, or None if they have no role yet."""
    view = perceived_by(events, resident)
    assigned = assignment(view, resident)
    if assigned is None:
        return None
    return Mind(
        resident=resident,
        role=assigned.role,
        persona=assigned.persona,
        teammates=assigned.teammates,
        memory=remember(view, resident),
        perceived=tuple(view),
    )
