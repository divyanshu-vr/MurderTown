"""Residents and the pool of names they are drawn from.

Names are short and none contains another, so a mention of one name in a
Statement can never be mistaken for a mention of a different Resident.
"""

from pydantic import BaseModel, ConfigDict

NAME_POOL: tuple[str, ...] = (
    "Ava", "Bram", "Cora", "Dax", "Elsie", "Finn", "Greta", "Hugo", "Iris", "Jonah",
    "Kit", "Luna", "Milo", "Nell", "Otto", "Pia", "Quinn", "Rosa", "Silas", "Tess",
    "Umar", "Vera", "Wren", "Xavi", "Yara", "Zane", "Bea", "Cyrus", "Dina", "Ezra",
)  # fmt: skip


class Resident(BaseModel):
    """A character in the town. The seat fixes their house and their place in every ordering."""

    model_config = ConfigDict(frozen=True)

    name: str
    seat: int
