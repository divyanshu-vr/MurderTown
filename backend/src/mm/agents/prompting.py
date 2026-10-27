"""Prompt assembly: everything an Agent is told, built only from what its Resident perceived.

A prompt has three parts, ordered from most to least stable so the model's
prompt cache is reused as much as possible:

- system: the rules, the Resident's role and persona. Byte-identical for the whole game.
- memory: the Resident's own notebook, journal and suspicions. Changes when they reflect.
- task: the game master's facts, what happened since the last reflection, and the decision.

Other Residents' words are untrusted text: they are wrapped in <statement> tags
and stripped of anything that could pass for markup.
"""

import hashlib
import re
from collections.abc import Sequence
from dataclasses import dataclass
from functools import cache
from pathlib import Path
from random import Random
from string import Template

from mm.agents.memory import Memory, remember
from mm.engine import Role
from mm.engine.decisions import DecisionKind, DecisionRequest
from mm.engine.events import (
    BallotCast,
    Event,
    PhaseStarted,
    ResidentDied,
    RoleAssigned,
    StatementMade,
    VoteResolved,
)
from mm.engine.perception import since_last_reflection
from mm.engine.phases import Phase
from mm.engine.state import GameState

TEMPLATES = Path(__file__).parent / "prompts"

STATEMENT_CHARACTERS_SHOWN = 600

DECISION_TEMPLATES = {
    DecisionKind.STATEMENT: "decisions/statement.md",
    DecisionKind.BALLOT: "decisions/ballot.md",
    DecisionKind.REFLECTION: "decisions/reflection.md",
}


@dataclass(frozen=True)
class Prompt:
    system: str
    memory: str
    task: str

    def user_message(self, task: str | None = None) -> str:
        """The memory and the task, as one message. A retry passes an amended task."""
        return f"{self.memory}\n\n{self.task if task is None else task}"


@cache
def template(path: str) -> Template:
    return Template((TEMPLATES / path).read_text(encoding="utf-8"))


def render(path: str, /, **values: object) -> str:
    return template(path).substitute(values).strip()


def prompt_version() -> str:
    """A short hash of every template, recorded with each model call."""
    digest = hashlib.sha256()
    for path in sorted(TEMPLATES.rglob("*.md")):
        digest.update(path.relative_to(TEMPLATES).as_posix().encode())
        digest.update(path.read_bytes())
    return digest.hexdigest()[:12]


def build_prompt(request: DecisionRequest, view: Sequence[Event], rng: Random) -> Prompt:
    """The prompt for one decision. `rng` only shuffles the listed options."""
    known = GameState.fold(view)
    briefing = next(
        event.payload
        for event in view
        if isinstance(event.payload, RoleAssigned) and event.payload.resident == request.resident
    )
    return Prompt(
        system=_system(known, briefing),
        memory=_memory(remember(view, request.resident)),
        task=_task(request, view, known, rng),
    )


def retry_task(prompt: Prompt, problem: str) -> str:
    return prompt.task + "\n" + render("retry.md", problem=problem)


def _system(known: GameState, briefing: RoleAssigned) -> str:
    assert known.config is not None
    if briefing.role is Role.MURDERER:
        mates = ", ".join(briefing.teammates)
        teammates = f"Your fellow Murderers are {mates}." if mates else "You are the only Murderer."
        role = render("roles/murderer.md", teammates=teammates)
    else:
        article = "a" if briefing.role is Role.CIVILIAN else "the"
        role = render("roles/town.md", role=f"{article} {briefing.role.capitalize()}")
    persona = briefing.persona
    return render(
        "system.md",
        name=briefing.resident,
        occupation=persona.occupation,
        residents=len(known.residents),
        max_days=known.config.max_days,
        role=role,
        temperament=persona.temperament,
        speaking_style=persona.speaking_style,
        quirk=persona.quirk,
    )


def _memory(memory: Memory) -> str:
    journal = [f"- Day {e.day}, {e.phase}: {e.text}" for e in memory.journal]
    suspicions = [f"- {name}: {s.suspicion} ({s.note})" for name, s in memory.suspicions.items()]
    return render(
        "memory.md",
        notebook=memory.notebook or "(empty)",
        journal="\n".join(journal) or "(no entries yet)",
        suspicions="\n".join(suspicions) or "(none yet)",
    )


def _task(request: DecisionRequest, view: Sequence[Event], known: GameState, rng: Random) -> str:
    recent = [
        line
        for event in since_last_reflection(view, request.resident)
        if event.phase is not Phase.SETUP and (line := _line(event))
    ]
    others = [name for name in known.living if name != request.resident]
    options = rng.sample(request.options, len(request.options))
    instructions = render(
        DECISION_TEMPLATES[request.kind],
        day=known.day,
        options=", ".join(options),
        others=", ".join(others),
    )
    return render(
        "task.md",
        facts="\n".join(_facts(view, known)),
        recent="\n".join(recent) or "(nothing yet)",
        instructions=instructions,
    )


def _facts(view: Sequence[Event], known: GameState) -> list[str]:
    living = [f"{r.name} ({r.occupation})" for r in known.residents if r.name not in known.dead]
    facts = [f"It is Day {known.day}.", f"Living Residents: {', '.join(living)}."]
    for event in view:
        match event.payload:
            case VoteResolved(tally=tally, skips=skips, banished=banished):
                ballots = ", ".join([*(f"{n} {v}" for n, v in tally.items()), f"skip {skips}"])
                outcome = f"{banished} was banished" if banished else "nobody was banished"
                facts.append(f"Day {event.day} Vote: {ballots}; {outcome}.")
            case ResidentDied(resident=resident, role=role):
                facts.append(f"{resident} is gone. They were a {role.capitalize()}.")
            case _:
                pass
    return facts


def _line(event: Event) -> str | None:
    """How one perceived event reads in an Agent's prompt; None for events it does not need."""
    match event.payload:
        case PhaseStarted(day=day, phase=phase):
            return f"[Day {day}: {phase.capitalize()}]"
        case StatementMade(speaker=speaker, text=text):
            return f'<statement speaker="{speaker}">{untrusted(text)}</statement>'
        case BallotCast(voter=voter, target=target):
            return f"{voter} voted for {target}." if target else f"{voter} voted to skip."
        case _:
            return None


def untrusted(text: str) -> str:
    """Another Resident's words, made safe to quote: no markup, one line, bounded length."""
    flat = re.sub(r"\s+", " ", re.sub(r"[<>`]", "", text)).strip()
    if len(flat) <= STATEMENT_CHARACTERS_SHOWN:
        return flat
    return flat[:STATEMENT_CHARACTERS_SHOWN].rstrip() + "..."
