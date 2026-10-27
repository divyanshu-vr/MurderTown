"""Casting: drawing the Residents and dealing their roles at the start of a game."""

from random import Random

from mm.engine.config import GameConfig
from mm.engine.events import EventPayload, GameStarted, RoleAssigned
from mm.engine.residents import NAME_POOL, Resident
from mm.engine.roles import Role


def cast(config: GameConfig, rng: Random) -> list[EventPayload]:
    """The opening events of a game: who lives in the town, then each Resident's secret role."""
    names = rng.sample(NAME_POOL, config.residents)
    residents = tuple(Resident(name=name, seat=seat) for seat, name in enumerate(names))
    deck = config.role_deck()
    rng.shuffle(deck)
    murderers = [name for name, role in zip(names, deck, strict=True) if role is Role.MURDERER]

    assignments = [
        RoleAssigned(
            resident=name,
            role=role,
            teammates=tuple(m for m in murderers if m != name) if role is Role.MURDERER else (),
        )
        for name, role in zip(names, deck, strict=True)
    ]
    return [GameStarted(config=config, residents=residents), *assignments]
