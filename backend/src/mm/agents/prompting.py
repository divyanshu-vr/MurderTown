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
from typing import assert_never

from mm.agents.memory import Memory, remember
from mm.engine import Role
from mm.engine.decisions import DecisionKind, DecisionRequest, StatementPart
from mm.engine.events import (
    AttackThwarted,
    BallotCast,
    BidPlaced,
    DecisionFellBack,
    DenMessagePosted,
    Event,
    GameEnded,
    GameStarted,
    KillVoteCast,
    LastWordsSpoken,
    PhaseStarted,
    RecapNarrated,
    ReflectionWritten,
    ResidentDied,
    ResidentInvestigated,
    ResidentProtected,
    RoleAssigned,
    SheriffFired,
    SheriffHeldFire,
    StatementMade,
    VictimChosen,
    VoteResolved,
)
from mm.engine.perception import briefing, since_last_reflection
from mm.engine.phases import Phase
from mm.engine.state import GameState

TEMPLATES = Path(__file__).parent / "prompts"

STATEMENT_CHARACTERS_SHOWN = 600

JOURNAL_ENTRIES_KEPT = 6
"""How many of the latest journal entries a prompt shows; the notebook carries the rest."""

DECISION_TEMPLATES = {
    DecisionKind.STATEMENT: "decisions/statement.md",
    DecisionKind.BID: "decisions/bid.md",
    DecisionKind.SHOWDOWN: "decisions/showdown.md",
    DecisionKind.BALLOT: "decisions/ballot.md",
    DecisionKind.LAST_WORDS: "decisions/last_words.md",
    DecisionKind.REFLECTION: "decisions/reflection.md",
    DecisionKind.DEN_MESSAGE: "decisions/den_message.md",
    DecisionKind.KILL_VOTE: "decisions/kill_vote.md",
    DecisionKind.PROTECT: "decisions/protect.md",
    DecisionKind.INVESTIGATE: "decisions/investigate.md",
    DecisionKind.RECAP: "decisions/recap.md",
}

POWERS = {
    Role.SHERIFF: "powers/sheriff.md",
    Role.DOCTOR: "powers/doctor.md",
    Role.DETECTIVE: "powers/detective.md",
}

MOMENTS: dict[StatementPart | None, str] = {
    "opening_round": "the Opening round of Discussion, where every Resident speaks once",
    "open_floor": "the Open floor, and you have won the turn to speak",
    None: "Discussion",
}

SHERIFF_FIRES: dict[str, str] = {
    "showdown": "In the Showdown each Day,",
    "night": "At Night,",
}

DEATHS: dict[str, str] = {
    "banished": "{resident} was banished on Day {day}. They were a {role}.",
    "shot": "{resident} died of the shot on Day {day}. They were a {role}.",
    "backfire": "{resident}, the Sheriff, died of the backfire on Day {day}.",
    "murdered": "{resident} was found murdered at Dawn on Day {day}. They were a {role}.",
}

WORDS_ASKED_FOR = {
    DecisionKind.STATEMENT: 60,
    DecisionKind.LAST_WORDS: 40,
    DecisionKind.DEN_MESSAGE: 40,
    DecisionKind.RECAP: 60,
}
"""How long anything said should be. Well under the engine's WORD_LIMIT, so the
engine only ever cuts a runaway answer."""


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
    if request.kind is DecisionKind.RECAP:
        return _recap_prompt(view, known)
    return Prompt(
        system=_system(known, briefing(view, request.resident)),
        memory=_memory(remember(view, request.resident), _private_knowledge(view)),
        task=_task(request, view, known, rng),
    )


def retry_task(prompt: Prompt, problem: str) -> str:
    return prompt.task + "\n" + render("retry.md", problem=problem)


def _system(known: GameState, assigned: RoleAssigned) -> str:
    assert known.config is not None
    if assigned.role is Role.MURDERER:
        mates = ", ".join(assigned.teammates)
        teammates = f"Your fellow Murderers are {mates}." if mates else "You are the only Murderer."
        role = render("roles/murderer.md", teammates=teammates)
    else:
        article = "a" if assigned.role is Role.CIVILIAN else "the"
        role = render("roles/town.md", role=f"{article} {assigned.role.capitalize()}")
    accuracy = _how_often(known.config.detective_accuracy)
    if power := POWERS.get(assigned.role):
        when = SHERIFF_FIRES[known.config.sheriff_shoots_at]
        role += "\n\n" + render(power, when=when, accuracy=accuracy)
    persona = assigned.persona
    return render(
        "system.md",
        name=assigned.resident,
        occupation=persona.occupation,
        residents=len(known.residents),
        max_days=known.config.max_days,
        accuracy=accuracy,
        role=role,
        temperament=persona.temperament,
        speaking_style=persona.speaking_style,
        quirk=persona.quirk,
    )


def _how_often(accuracy: float) -> str:
    """The Detective's accuracy as a Resident would say it: "about 80% of the time"."""
    return f"about {accuracy:.0%} of the time"


def _memory(memory: Memory, private: list[str]) -> str:
    recent = memory.journal[-JOURNAL_ENTRIES_KEPT:]
    journal = [f"- Day {e.day}, {e.phase}: {e.text}" for e in recent]
    suspicions = [f"- {s.resident}: {s.suspicion} ({s.note})" for s in memory.dossier]
    return render(
        "memory.md",
        notebook=memory.notebook or "(empty)",
        journal="\n".join(journal) or "(no entries yet)",
        suspicions="\n".join(suspicions) or "(none yet)",
        private="\n".join(private) or "(nothing)",
    )


def _private_knowledge(view: Sequence[Event]) -> list[str]:
    """What the Resident's role has taught them at Night. Only they perceive these events."""
    known: list[str] = []
    for event in view:
        match event.payload:
            case ResidentProtected(target=target):
                known.append(f"- Night of Day {event.day}: you protected {target}.")
            case ResidentInvestigated(target=target, found_murderer=found):
                finding = "murderer" if found else "not murderer"
                known.append(
                    f'- Night of Day {event.day}: your investigation of {target} said "{finding}".'
                )
            case _:
                pass
    return known


def _recap_prompt(view: Sequence[Event], known: GameState) -> Prompt:
    """The narrator's prompt: the facts and every public event since the previous Dawn.

    The narrator perceives only what the whole town does and keeps no notes, so
    its window is one Day, however long the game runs.
    """
    since_yesterday = [event for event in view if event.day >= known.day - 1]
    recent = [line for event in since_yesterday if (line := _line(event))]
    return Prompt(
        system=render("narrator.md", residents=len(known.residents)),
        memory="You keep no notes: each recap is written fresh from the facts and the Day.",
        task=render(
            DECISION_TEMPLATES[DecisionKind.RECAP],
            day=known.day,
            facts="\n".join(_facts(view, known)),
            recent="\n".join(recent) or "(nothing yet)",
            words=WORDS_ASKED_FOR[DecisionKind.RECAP],
        ),
    )


def _task(request: DecisionRequest, view: Sequence[Event], known: GameState, rng: Random) -> str:
    recent = [
        line
        for event in since_last_reflection(view, request.resident)
        if event.phase is not Phase.SETUP and (line := _line(event))
    ]
    options = rng.sample(request.options, len(request.options))
    instructions = render(
        DECISION_TEMPLATES[request.kind],
        day=known.day,
        options=", ".join(options),
        moment=MOMENTS[request.part],
        words=WORDS_ASKED_FOR.get(request.kind),
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
            case SheriffFired(sheriff=sheriff, target=target):
                facts.append(f"Day {event.day}: {sheriff}, the Sheriff, fired at {target}.")
            case ResidentDied(resident=resident, cause=cause, role=role):
                death = DEATHS[cause].format(
                    resident=resident, day=event.day, role=role.capitalize()
                )
                facts.append(death)
            case AttackThwarted(saved=saved):
                who = saved or "someone"
                facts.append(f"At Dawn on Day {event.day}: {who} was attacked, but survived.")
            case _:
                pass
    return facts


def _line(event: Event) -> str | None:  # noqa: C901 - one case per event type
    """How one perceived event reads in an Agent's prompt; None for events it does not need."""
    match event.payload:
        case PhaseStarted(day=day, phase=phase):
            return f"[Day {day}: {phase.capitalize()}]"
        case StatementMade(speaker=speaker, text=text):
            return _quoted(speaker, text)
        case BallotCast(voter=voter, target=target):
            return f"{voter} voted for {target}." if target else f"{voter} voted to skip."
        case LastWordsSpoken(resident=resident, text=text):
            return _quoted(resident, text, "last words")
        case DenMessagePosted(murderer=murderer, text=text, proposed_victim=proposal):
            proposed = f" {murderer} proposes {proposal}." if proposal else ""
            return _quoted(murderer, text, "in the Den") + proposed
        case KillVoteCast(murderer=murderer, target=target):
            return f"{murderer} voted to kill {target}."
        case VictimChosen(victim=victim):
            return f"The Den chose {victim} as tonight's Victim."
        case VoteResolved() | ResidentDied() | SheriffFired() | AttackThwarted():
            return None  # shown among the game master's facts instead
        case (
            GameStarted() | RoleAssigned() | ReflectionWritten()
            | ResidentProtected() | ResidentInvestigated()
        ):  # fmt: skip
            return None  # shown in the briefing or the Resident's own memory instead
        case BidPlaced() | SheriffHeldFire() | GameEnded() | DecisionFellBack() | RecapNarrated():
            return None  # not needed for a decision (Residents saw what a recap tells), or unseen
        case unknown:
            assert_never(unknown)


def _quoted(speaker: str, text: str, aside: str | None = None) -> str:
    """Another Resident's words, wrapped as an untrusted statement, with an optional aside."""
    said = f"({aside}) {untrusted(text)}" if aside else untrusted(text)
    return f'<statement speaker="{speaker}">{said}</statement>'


def untrusted(text: str) -> str:
    """Another Resident's words, made safe to quote: no markup, one line, bounded length."""
    flat = re.sub(r"\s+", " ", re.sub(r"[<>`]", "", text)).strip()
    if len(flat) <= STATEMENT_CHARACTERS_SHOWN:
        return flat
    return flat[:STATEMENT_CHARACTERS_SHOWN].rstrip() + "..."
