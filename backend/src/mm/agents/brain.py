"""The decision-source interface: anything that can play a Resident."""

from collections.abc import Callable, Sequence
from random import Random
from typing import Protocol

from mm.engine import Resident
from mm.engine.decisions import Answer, DecisionRequest
from mm.engine.events import Event


class Brain(Protocol):
    """Plays one Resident. Scripted bots, LLM Agents and (later) humans all fit this shape.

    `view` holds only the events this Resident may perceive, so a Brain cannot
    learn anything its character could not know. The answer says which decision
    was made, and why a default was used instead if the Brain could not decide.
    A Brain whose model gave no answer at all raises `ModelFailureError`, which stops the game.
    """

    async def decide(self, request: DecisionRequest, view: Sequence[Event]) -> Answer: ...


class ModelFailureError(Exception):
    """The model timed out or failed on a decision, so the game cannot go on.

    `problem` says what went wrong, in words safe to show Spectators.
    """

    def __init__(self, request: DecisionRequest, problem: str) -> None:
        super().__init__(f"{request.resident}'s {request.kind}: {problem}")
        self.request, self.problem = request, problem


BrainFactory = Callable[[Resident], Brain]


def own_random(seed: int, resident: Resident) -> Random:
    """A Resident's own draws, the same in every run of a game with this seed."""
    return Random(f"{seed}:{resident.name}")
