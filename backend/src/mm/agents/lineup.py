"""Lineups: every Resident's Brain, as the game's configuration says who plays them."""

from collections.abc import Mapping, Sequence

from mm.agents.brain import Brain, BrainFactory, own_random
from mm.agents.calls import CallRecorder, ModelCall
from mm.agents.llm_brain import LLMBrain
from mm.agents.scripted import ScriptedBot
from mm.engine import GameConfig, PlayedBy, Resident
from mm.engine.casting import seated_roles
from mm.llm import ModelProvider
from mm.llm.prices import price_of


def lineup_brains(
    config: GameConfig,
    providers: Mapping[str, ModelProvider],
    record: CallRecorder,
    recorded: Sequence[ModelCall] = (),
) -> BrainFactory:
    """A factory giving each Resident a scripted bot or an Agent, as the lineup says.

    Sides are known before the game starts (`seated_roles`), so each seat's choice is
    settled here, and a lineup that names a provider not available or a model with no
    price is refused before anything is played. A resumed game passes the model calls
    it had `recorded`, which answer again.
    """
    lineup = config.lineup
    chosen = {
        seat: lineup.played_by(seat, role.side) for seat, role in seated_roles(config).items()
    }
    for played_by in {*chosen.values(), lineup.everyone}:
        _check(played_by, providers)
    by_key = {call.key: call for call in recorded}

    def make(resident: Resident) -> Brain:
        played_by = chosen.get(resident.seat, lineup.everyone)  # the narrator has no seat
        rng = own_random(config.seed, resident)
        if played_by.provider == "scripted":
            return ScriptedBot(rng)
        return LLMBrain(providers[played_by.provider], played_by, record, rng, by_key)

    return make


def _check(played_by: PlayedBy, providers: Mapping[str, ModelProvider]) -> None:
    if played_by.provider == "scripted":
        return
    try:
        providers[played_by.provider]
    except KeyError:
        raise ValueError(f"no provider called {played_by.provider} is available") from None
    price_of(played_by.model)
