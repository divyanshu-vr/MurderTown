"""The decision-source interface: anything that can play a Resident."""

from collections.abc import Callable, Sequence
from typing import Protocol

from mm.engine import Resident
from mm.engine.decisions import Answer, DecisionRequest
from mm.engine.events import Event


class Brain(Protocol):
    """Plays one Resident. Scripted bots, LLM Agents and (later) humans all fit this shape.

    `view` holds only the events this Resident may perceive, so a Brain cannot
    learn anything its character could not know. The answer says which decision
    was made, and why a default was used instead if the Brain could not decide.
    """

    async def decide(self, request: DecisionRequest, view: Sequence[Event]) -> Answer: ...


BrainFactory = Callable[[Resident], Brain]
