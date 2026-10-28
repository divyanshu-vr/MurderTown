"""Casting: drawing the Residents and dealing their roles and personas at the start of a game."""

from random import Random

from mm.engine.config import GameConfig
from mm.engine.events import EventPayload, GameConfigured, GameStarted, RoleAssigned
from mm.engine.personas import PERSONAS
from mm.engine.residents import NAME_POOL, Resident
from mm.engine.roles import Role


def seated_roles(config: GameConfig) -> dict[int, Role]:
    """The role at each seat, known before the game starts: casting is the first thing a game
    draws from its seeded Random, so dealing again from a fresh one deals the same roles."""
    seats: dict[str, int] = {}
    roles: dict[int, Role] = {}
    for payload in cast(config, Random(config.seed)):
        if isinstance(payload, GameStarted):
            seats = {resident.name: resident.seat for resident in payload.residents}
        elif isinstance(payload, RoleAssigned):
            roles[seats[payload.resident]] = payload.role
    return roles


def cast(config: GameConfig, rng: Random) -> list[EventPayload]:
    """The opening events of a game: the Host's configuration (for Spectators), who lives in the
    town and the rules they play by, then each Resident's secret role."""
    names = rng.sample(NAME_POOL, config.residents)
    personas = rng.sample(PERSONAS, config.residents)
    residents = tuple(
        Resident(name=name, seat=seat, occupation=persona.occupation)
        for seat, (name, persona) in enumerate(zip(names, personas, strict=True))
    )
    deck = config.role_deck()
    rng.shuffle(deck)
    murderers = [name for name, role in zip(names, deck, strict=True) if role is Role.MURDERER]

    assignments = [
        RoleAssigned(
            resident=name,
            role=role,
            persona=persona,
            teammates=tuple(m for m in murderers if m != name) if role is Role.MURDERER else (),
        )
        for name, role, persona in zip(names, deck, personas, strict=True)
    ]
    return [
        GameConfigured(config=config),
        GameStarted(rules=config.rules, residents=residents),
        *assignments,
    ]
