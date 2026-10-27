"""An Agent's memory, folded from its own reflections. There is no separate memory store.

Each reflection rewrites the notebook in full and adds a journal entry, so the
newest notebook plus the last few entries carry everything forward while the
amount of text stays the same however long the game runs.
"""

from collections.abc import Sequence
from dataclasses import dataclass

from mm.engine.decisions import Suspicion
from mm.engine.events import Event, ReflectionWritten
from mm.engine.phases import Phase

JOURNAL_ENTRIES_KEPT = 6


@dataclass(frozen=True)
class JournalEntry:
    day: int
    phase: Phase
    text: str


@dataclass(frozen=True)
class Memory:
    notebook: str
    journal: tuple[JournalEntry, ...]
    suspicions: dict[str, Suspicion]
    """The latest opinion about each other Resident, by name."""


def remember(view: Sequence[Event], resident: str) -> Memory:
    notebook = ""
    journal: list[JournalEntry] = []
    suspicions: dict[str, Suspicion] = {}
    for event in view:
        reflection = event.payload
        if not isinstance(reflection, ReflectionWritten) or reflection.resident != resident:
            continue
        notebook = reflection.notebook or notebook
        if reflection.journal_entry:
            journal.append(JournalEntry(event.day, event.phase, reflection.journal_entry))
        suspicions.update({s.resident: s for s in reflection.suspicions})
    return Memory(
        notebook=notebook,
        journal=tuple(journal[-JOURNAL_ENTRIES_KEPT:]),
        suspicions=dict(sorted(suspicions.items())),
    )
