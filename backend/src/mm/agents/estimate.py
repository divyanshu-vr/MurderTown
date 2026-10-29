"""A game's Expected cost: its Equivalent cost before it starts, by model.

A game's calls follow from its setup. The estimate plays a typical game on paper: a Town
Resident dies every Night, and the Votes banish a Town Resident and a Murderer in turn, until
one side wins or the Days run out. Each Day every living Resident reflects at Dawn and after
the Vote, makes an Opening Statement and their share of the Open floor's, Bids on every Turn,
votes, and talks at Dusk; at Night the Murderers meet and vote, the Doctor protects and the
Detective investigates. Each seat's calls are weighted by the chance it is still alive.

Each call is priced at its model's list price, from the tokens measured for its decision kind
in live games on 2026-10-29 at medium effort (`MEASURED`). A kind a model was not measured on
takes the default model's prompt and that model's typical answer; a model not measured at all
is priced on the default model's tokens. A scripted seat costs nothing.
"""

from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass, field, replace
from statistics import median

from pydantic import BaseModel

from mm.engine import GameConfig, PlayedBy, Role, Side
from mm.engine.casting import seated_roles
from mm.engine.decisions import DecisionKind
from mm.engine.dusk import MESSAGES_PER_CONVERSATION
from mm.llm.prices import equivalent_cost
from mm.llm.protocol import Usage

DEFAULT_MODEL = PlayedBy().model
"""Haiku: its tokens price a model not measured."""


def measured(cached: int, written: int, output: int) -> Usage:
    """A decision kind's average call: tokens read from the cache (the briefing), written to
    it (the rest of the prompt), and its answer with any thinking."""
    return Usage(cache_read_tokens=cached, cache_write_5m_tokens=written, output_tokens=output)


MEASURED: dict[str, dict[DecisionKind, Usage]] = {
    DEFAULT_MODEL: {  # medium effort, Bids at low
        DecisionKind.BALLOT: measured(cached=2990, written=3980, output=410),
        DecisionKind.BID: measured(cached=3390, written=1440, output=380),
        DecisionKind.CONVERSATION_MESSAGE: measured(cached=3110, written=2180, output=780),
        DecisionKind.DEN_MESSAGE: measured(cached=0, written=4270, output=480),
        DecisionKind.DUSK_INTENT: measured(cached=2980, written=2030, output=350),
        DecisionKind.INVESTIGATE: measured(cached=1880, written=3120, output=270),
        DecisionKind.KILL_VOTE: measured(cached=3230, written=1550, output=290),
        DecisionKind.LAST_WORDS: measured(cached=3200, written=3990, output=1160),
        DecisionKind.PROTECT: measured(cached=1040, written=3480, output=300),
        DecisionKind.RECAP: measured(cached=0, written=3000, output=730),
        DecisionKind.REFLECTION: measured(cached=2320, written=3410, output=1930),
        DecisionKind.SHOWDOWN: measured(cached=3170, written=3880, output=380),
        DecisionKind.STATEMENT: measured(cached=3010, written=2840, output=1250),
    },
    "claude-sonnet-5-5": {  # measured as Murderers, so for their decisions only
        DecisionKind.BALLOT: measured(cached=3240, written=3970, output=140),
        DecisionKind.BID: measured(cached=3260, written=1310, output=110),
        DecisionKind.CONVERSATION_MESSAGE: measured(cached=3240, written=2000, output=150),
        DecisionKind.DEN_MESSAGE: measured(cached=1620, written=3220, output=130),
        DecisionKind.DUSK_INTENT: measured(cached=3240, written=1910, output=120),
        DecisionKind.KILL_VOTE: measured(cached=3240, written=1900, output=90),
        DecisionKind.LAST_WORDS: measured(cached=3240, written=4180, output=200),
        DecisionKind.REFLECTION: measured(cached=3240, written=2910, output=640),
        DecisionKind.STATEMENT: measured(cached=3240, written=3080, output=290),
    },
}

MESSAGES_AT_DUSK = MESSAGES_PER_CONVERSATION / 2
"""Conversation messages per living Resident each Dusk: everyone paired, talking it out."""


SEATINGS = 24
"""A setup with no seed is priced as the average of this many seatings: the game deals a
random one, and which seats are Murderers matters when seats are played differently."""


class Estimate(BaseModel):
    """A game's Expected cost, by model, and how many Days the paper game ran."""

    usd: float
    by_model: dict[str, float]
    days: int


def estimate(config: GameConfig, seeded: bool = True) -> Estimate:
    """The Expected cost of a game of `config`, played as `config.lineup` says; with no seed
    chosen (not `seeded`), averaged over `SEATINGS` seatings. The narrator is played as
    everyone is."""
    seeds = [config.seed] if seeded else list(range(SEATINGS))
    by_model: dict[str, float] = defaultdict(float)
    for seed in seeds:
        game = PaperGame(seated_roles(config.model_copy(update={"seed": seed})))
        game.play(config)
        for seat, role in game.roles.items():
            played_by = config.lineup.played_by(seat, role.side)
            if not played_by.scripted:
                by_model[played_by.model] += _priced(played_by.model, game.calls[seat]) / len(seeds)
        narrator = config.lineup.everyone
        if not narrator.scripted:
            recaps: Calls = {DecisionKind.RECAP: game.days - 1}
            by_model[narrator.model] += _priced(narrator.model, recaps) / len(seeds)
    return Estimate(usd=sum(by_model.values()), by_model=dict(by_model), days=game.days)


Calls = dict[DecisionKind, float]
"""How many calls of each kind one seat is expected to make, alive or not."""


@dataclass
class PaperGame:
    """A typical game played on paper, counting each seat's calls."""

    roles: dict[int, Role]
    days: int = 1
    calls: dict[int, Calls] = field(init=False)
    seated: dict[Side, int] = field(init=False)
    living: dict[Side, int] = field(init=False)

    def __post_init__(self) -> None:
        self.calls = {seat: defaultdict(float) for seat in self.roles}
        self.seated = {side: sum(r.side is side for r in self.roles.values()) for side in Side}
        self.living = dict(self.seated)

    def play(self, config: GameConfig) -> None:
        """Day 1's Night, then whole Days until a side wins or the Days run out."""
        self.night()
        while self.days < config.max_days and not self.won:
            self.day(config)

    def day(self, config: GameConfig) -> None:
        self.days += 1
        banished = Side.TOWN if self.days % 2 == 0 else Side.MURDERERS  # in turn, from Day 2
        self.ask(DecisionKind.REFLECTION, 1)
        statements = 1 + config.open_floor_statements / sum(self.living.values())
        self.ask(DecisionKind.STATEMENT, statements)
        self.ask(DecisionKind.BID, config.open_floor_statements)
        self.ask(DecisionKind.SHOWDOWN, 1, who=lambda role: role is Role.SHERIFF)
        self.ask(DecisionKind.BALLOT, 1)
        self.ask(DecisionKind.LAST_WORDS, 1 / self.living[banished], who=_on_side(banished))
        self.living[banished] -= 1
        if self.won:
            return
        self.ask(DecisionKind.REFLECTION, 1)
        self.ask(DecisionKind.DUSK_INTENT, 1)
        self.ask(DecisionKind.CONVERSATION_MESSAGE, MESSAGES_AT_DUSK)
        self.night()

    def night(self) -> None:
        if self.living[Side.MURDERERS] > 1:
            self.ask(DecisionKind.DEN_MESSAGE, 1, who=_on_side(Side.MURDERERS))
        self.ask(DecisionKind.KILL_VOTE, 1, who=_on_side(Side.MURDERERS))
        self.ask(DecisionKind.PROTECT, 1, who=lambda role: role is Role.DOCTOR)
        self.ask(DecisionKind.INVESTIGATE, 1, who=lambda role: role is Role.DETECTIVE)
        self.living[Side.TOWN] -= 1  # murdered

    def ask(
        self, kind: DecisionKind, times: float, who: Callable[[Role], bool] = lambda _: True
    ) -> None:
        """Each seat whose role is `who` makes `times` calls of `kind`, weighted by the chance
        it is still alive."""
        for seat, role in self.roles.items():
            if who(role):
                alive = self.living[role.side] / self.seated[role.side]
                self.calls[seat][kind] += times * alive

    @property
    def won(self) -> bool:
        """Whether a side has won: every Murderer banished, or as many Murderers as Town."""
        murderers = self.living[Side.MURDERERS]
        return murderers == 0 or murderers >= self.living[Side.TOWN]


def _on_side(side: Side) -> Callable[[Role], bool]:
    return lambda role: role.side is side


def _priced(model: str, calls: Calls) -> float:
    """What `calls` cost on `model`, from the tokens measured for each kind."""
    return sum(
        times * equivalent_cost(model, _measured(model, kind)) for kind, times in calls.items()
    )


def _measured(model: str, kind: DecisionKind) -> Usage:
    """A call of `kind` on `model`, as measured; for a kind the model was not measured on, the
    default model's prompt with the model's typical (median) answer."""
    default = MEASURED[DEFAULT_MODEL][kind]
    measurements = MEASURED.get(model)
    if measurements is None:
        return default
    if kind in measurements:
        return measurements[kind]
    typical = median(usage.output_tokens for usage in measurements.values())
    return replace(default, output_tokens=round(typical))
