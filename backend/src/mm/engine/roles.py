"""Roles and sides.

A Resident's role decides what they may do; their side decides who wins with whom.
Every role except Murderer is on the Town's side.
"""

from enum import StrEnum


class Side(StrEnum):
    TOWN = "town"
    MURDERERS = "murderers"


class Role(StrEnum):
    MURDERER = "murderer"
    DOCTOR = "doctor"
    DETECTIVE = "detective"
    SHERIFF = "sheriff"
    CIVILIAN = "civilian"

    @property
    def side(self) -> Side:
        return Side.MURDERERS if self is Role.MURDERER else Side.TOWN
