"""The six Phases of a Day, plus the moments before the first Day and after the last."""

from enum import StrEnum


class Phase(StrEnum):
    SETUP = "setup"
    DAWN = "dawn"
    DISCUSSION = "discussion"
    SHOWDOWN = "showdown"
    VOTE = "vote"
    DUSK = "dusk"
    NIGHT = "night"
    ENDED = "ended"
