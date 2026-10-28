"""Lineups: every Resident's Brain, as the game's configuration says who plays them."""

from collections.abc import Callable, Mapping, Sequence

from mm.agents.brain import Brain, BrainFactory, own_random
from mm.agents.calls import CallRecorder, ModelCall
from mm.agents.llm_brain import LLMBrain
from mm.agents.scripted import InjectionProber, ScriptedBot
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

    def choose(resident: Resident) -> PlayedBy:
        return chosen.get(resident.seat, lineup.everyone)  # the narrator has no seat

    choices = {*chosen.values(), lineup.everyone}
    return _brains(choose, choices, providers, record=record, seed=config.seed, recorded=recorded)


def llm_agents(
    provider: ModelProvider,
    played_by: PlayedBy,
    record: CallRecorder,
    seed: int,
    recorded: Sequence[ModelCall] = (),
) -> BrainFactory:
    """A factory giving every Resident its own Agent on one provider and model."""
    providers = {played_by.provider: provider}
    return _brains(
        lambda resident: played_by,
        {played_by},
        providers,
        record=record,
        seed=seed,
        recorded=recorded,
    )


def _brains(
    choose: Callable[[Resident], PlayedBy],
    choices: set[PlayedBy],
    providers: Mapping[str, ModelProvider],
    *,
    record: CallRecorder,
    seed: int,
    recorded: Sequence[ModelCall],
) -> BrainFactory:
    for played_by in choices:
        _check(played_by, providers)
    by_key = {call.key: call for call in recorded}

    def make(resident: Resident) -> Brain:
        played_by = choose(resident)
        rng = own_random(seed, resident)
        if played_by.scripted:
            return InjectionProber(rng) if played_by.probes else ScriptedBot(rng)
        return LLMBrain(providers[played_by.provider], played_by, record, rng, by_key)

    return make


def _check(played_by: PlayedBy, providers: Mapping[str, ModelProvider]) -> None:
    """Refuse a choice nobody can play: a provider not available, or a model with no price."""
    if played_by.scripted:
        return
    if played_by.provider not in providers:
        raise ValueError(f"no provider called {played_by.provider} is available")
    providers[played_by.provider]  # made now, so a missing key or login is reported here
    price_of(played_by.model)
