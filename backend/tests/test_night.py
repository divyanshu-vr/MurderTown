"""Seam 1: the Night. The Den, the kill, the Doctor and the Detective, and what Dawn reveals."""

import asyncio
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from random import Random

import pytest

from mm.agents import Brain, BrainFactory, scripted_bots
from mm.engine import GameConfig, Phase, Resident, Role, Side
from mm.engine.decisions import Answer, DecisionKind, DecisionRequest, Target
from mm.engine.events import (
    AttackThwarted,
    DenMessagePosted,
    Event,
    GameEnded,
    KillVoteCast,
    RecapNarrated,
    ResidentDied,
    ResidentInvestigated,
    ResidentProtected,
    RolesRevealed,
    VictimChosen,
)
from mm.engine.state import GameState
from mm.orchestrator import play_game
from tests.support import (
    Asked,
    Delayed,
    Puppet,
    Requests,
    everyone_alive_on_day_two,
    everyone_votes_for,
    name_at_seat,
    payloads,
    play_opening_night,
    puppets,
    seats_by_role,
    wrapped,
)

CONFIG = GameConfig(residents=8, murderers=2, max_days=2, seed=9, open_floor_seconds=None)
SIX = GameConfig(residents=6, murderers=1, max_days=4, seed=2, open_floor_seconds=None)


async def requests_and_log(
    config: GameConfig, factory: BrainFactory
) -> tuple[Requests, list[Event]]:
    asked: Requests = []
    result = await play_game(config, wrapped(factory, lambda brain: Asked(brain, asked)))
    return asked, result.events


def of_kind(asked: Requests, kind: DecisionKind) -> list[DecisionRequest]:
    return [request for request, _ in asked if request.kind is kind]


async def six_seats() -> tuple[int, int, int, int, int, int]:
    """In the six-Resident game: the Murderer, Doctor, Detective, Sheriff and two Civilians."""
    roles = seats_by_role(SIX)
    (murderer,), (doctor,), (detective,) = (
        roles[Role.MURDERER],
        roles[Role.DOCTOR],
        roles[Role.DETECTIVE],
    )
    (sheriff,), (first, second) = roles[Role.SHERIFF], roles[Role.CIVILIAN]
    return murderer, doctor, detective, sheriff, first, second


# --- The Den and the kill ---------------------------------------------------------------


async def test_murderers_speak_in_the_den_one_after_another_each_hearing_the_last() -> None:
    murderers = seats_by_role(CONFIG)[Role.MURDERER]
    asked, events = await requests_and_log(CONFIG, puppets())

    den = [(request, view) for request, view in asked if request.kind is DecisionKind.DEN_MESSAGE]
    (first, _), (second, heard_before_speaking) = den[0], den[1]
    assert [first.resident, second.resident] == [name_at_seat(events, s) for s in murderers]
    heard = payloads(heard_before_speaking, DenMessagePosted)
    assert [message.murderer for message in heard] == [first.resident]


async def test_a_lone_murderer_is_not_asked_to_speak_in_the_den_but_simply_picks() -> None:
    asked, events = await requests_and_log(SIX.model_copy(update={"max_days": 2}), puppets())

    assert of_kind(asked, DecisionKind.DEN_MESSAGE) == []
    (vote,) = payloads(events, KillVoteCast, day=1)
    (chosen,) = payloads(events, VictimChosen, day=1)
    assert chosen.victim == vote.target


@dataclass(frozen=True)
class SplitDen(Puppet):
    """Each Murderer's kill vote is scripted on its own, by their seat."""

    kill_by_murderer: Mapping[int, int] = field(default_factory=dict)

    async def decide(self, request: DecisionRequest, view: Sequence[Event]) -> Answer:
        if request.kind is DecisionKind.KILL_VOTE:
            known = GameState.fold(view)
            me = next(r.seat for r in known.residents if r.name == request.resident)
            target = known.residents[self.kill_by_murderer[me]].name
            return Answer(Target(target=target, reason="scripted"))
        return await super().decide(request, view)


async def test_the_most_chosen_resident_becomes_the_victim() -> None:
    config = GameConfig(residents=12, murderers=3, seed=4, open_floor_seconds=None)
    roles = seats_by_role(config)
    one, two, three = roles[Role.MURDERER]
    first, second = roles[Role.CIVILIAN][:2]
    split = SplitDen(kill_by_murderer={one: first, two: first, three: second})

    events = await play_opening_night(config, lambda _: split)

    (chosen,) = payloads(events, VictimChosen)
    assert chosen.victim == name_at_seat(events, first)


async def test_a_tied_kill_vote_is_drawn_the_same_way_for_the_same_seed() -> None:
    winners: set[int] = set()
    for seed in range(40):
        config = CONFIG.model_copy(update={"seed": seed})
        roles = seats_by_role(config)
        one, two = roles[Role.MURDERER]
        candidates = roles[Role.CIVILIAN][:2]
        split = SplitDen(kill_by_murderer={one: candidates[0], two: candidates[1]})

        played = [await play_opening_night(config, lambda _, s=split: s) for _ in range(2)]

        chosen = [payloads(events, VictimChosen)[0].victim for events in played]
        names = [name_at_seat(played[0], seat) for seat in candidates]
        assert chosen[0] == chosen[1]
        winners.add(names.index(chosen[0]))
    assert winners == {0, 1}  # over many seeds, each side of the tie wins sometimes


# --- The Doctor ---------------------------------------------------------------------------


@pytest.mark.parametrize("names_the_saved", [True, False])
async def test_a_protected_victim_survives_and_dawn_says_so(names_the_saved: bool) -> None:
    config = CONFIG.model_copy(update={"dawn_names_the_saved": names_the_saved})
    civilian = seats_by_role(config)[Role.CIVILIAN][0]

    result = await play_game(config, puppets(kills={1: civilian}, protects={1: civilian}))

    (thwarted,) = payloads(result.events, AttackThwarted)
    saved = name_at_seat(result.events, civilian)
    assert thwarted.saved == (saved if names_the_saved else None)
    assert [d for d in payloads(result.events, ResidentDied) if d.cause == "murdered"] == []


async def test_the_doctor_never_protects_one_resident_twice_running_nor_themselves_twice() -> None:
    config = CONFIG.model_copy(update={"max_days": 3})
    roles = seats_by_role(config)
    (doctor,), (detective,) = roles[Role.DOCTOR], roles[Role.DETECTIVE]
    civilians, (murderer, _) = roles[Role.CIVILIAN], roles[Role.MURDERER]
    nights = {"kills": {1: civilians[0], 2: civilians[1], 3: civilians[2]},
              "protects": {1: doctor, 2: detective, 3: murderer}}  # fmt: skip

    asked, events = await requests_and_log(config, puppets(**nights))

    protects = of_kind(asked, DecisionKind.PROTECT)
    assert len(protects) == 3
    doctor_name, detective_name = name_at_seat(events, doctor), name_at_seat(events, detective)
    assert doctor_name in protects[0].options
    assert doctor_name not in protects[1].options  # protected last Night
    assert detective_name not in protects[2].options  # protected last Night
    assert doctor_name not in protects[2].options  # has protected themselves once already


# --- The Detective -------------------------------------------------------------------------


async def test_the_detective_never_investigates_twice_and_is_not_asked_once_all_are_known() -> None:
    murderer, doctor, detective, sheriff, first, second = await six_seats()
    nights = {
        "kills": {1: first, 2: sheriff, 3: second, 4: doctor},
        "protects": {1: detective, 2: murderer, 3: detective, 4: murderer},
        "investigations": {1: murderer, 2: doctor, 3: second},
    }

    asked, events = await requests_and_log(SIX, puppets(**nights))

    investigations = of_kind(asked, DecisionKind.INVESTIGATE)
    assert len(investigations) == 3  # on the fourth Night, everyone still alive is known
    targets = [found.target for found in payloads(events, ResidentInvestigated)]
    assert len(set(targets)) == len(targets)
    for done, request in enumerate(investigations):
        assert not set(targets[:done]) & set(request.options)


async def investigated_wrongly(config: GameConfig, target_role: Role, games: int) -> float:
    """How often the Detective's one finding is wrong, over many seeded one-Night games."""
    wrong = 0
    for seed in range(games):
        seeded = config.model_copy(update={"seed": seed})
        target = seats_by_role(seeded)[target_role][0]
        events = await play_opening_night(seeded, puppets(investigations={1: target}))
        (found,) = payloads(events, ResidentInvestigated)
        wrong += found.found_murderer != (target_role is Role.MURDERER)
    return wrong / games


@pytest.mark.parametrize("accuracy", [0.8, 0.6])
@pytest.mark.parametrize("target_role", [Role.MURDERER, Role.CIVILIAN])
async def test_the_detective_is_wrong_about_as_often_as_the_configured_accuracy_says(
    accuracy: float, target_role: Role
) -> None:
    config = SIX.model_copy(update={"detective_accuracy": accuracy})

    error = await investigated_wrongly(config, target_role, games=400)

    assert abs(error - (1 - accuracy)) < 0.07  # about three standard deviations at 400 games


async def test_a_detective_with_perfect_accuracy_is_never_wrong() -> None:
    config = SIX.model_copy(update={"detective_accuracy": 1.0})

    assert await investigated_wrongly(config, Role.MURDERER, games=30) == 0


# --- Dawn and the end of the game ----------------------------------------------------------


async def test_dawn_announces_the_news_then_the_recap_then_residents_reflect() -> None:
    civilian = seats_by_role(CONFIG)[Role.CIVILIAN][0]

    result = await play_game(CONFIG, puppets(kills={1: civilian}))

    dawn = [type(e.payload).__name__ for e in result.events if (e.day, e.phase) == (2, Phase.DAWN)]
    assert dawn[:4] == ["PhaseStarted", "ResidentDied", "RecapNarrated", "ReflectionWritten"]
    assert set(dawn[3:]) == {"ReflectionWritten"}


async def test_a_murder_that_decides_the_game_ends_it_at_once() -> None:
    murderer, doctor, detective, sheriff, first, second = await six_seats()
    ballots = {2: everyone_votes_for(first), 3: everyone_votes_for(sheriff)}
    nights = {"kills": {1: first, 2: second, 3: detective},  # the first Victim is saved
              "protects": {1: first, 2: detective, 3: murderer}}  # fmt: skip

    result = await play_game(SIX, puppets(ballots, **nights))

    murder = next(e for e in result.events if isinstance(e.payload, ResidentDied) and e.day == 4)
    after = [type(event.payload) for event in result.events[murder.seq :]]
    assert after == [RolesRevealed, GameEnded]  # the very next events
    assert payloads(result.events, RecapNarrated, day=4) == []
    assert result.state.winner is Side.MURDERERS
    assert name_at_seat(result.events, doctor) in result.state.living


async def test_a_night_shot_that_kills_the_last_murderer_ends_the_game_before_anyone_acts() -> None:
    config = SIX.model_copy(update={"sheriff_shoots_at": "night"})
    murderer, *_ = await six_seats()

    result = await play_game(config, puppets(shots={2: murderer}, **everyone_alive_on_day_two(SIX)))

    assert result.state.winner is Side.TOWN
    assert payloads(result.events, KillVoteCast, day=2) == []
    assert payloads(result.events, ResidentProtected, day=2) == []
    assert isinstance(result.events[-3].payload, ResidentDied)  # then every role, and the end


async def test_a_night_backfire_that_leaves_the_murderers_level_ends_the_game_at_once() -> None:
    config = SIX.model_copy(update={"sheriff_shoots_at": "night"})
    _, doctor, detective, _, first, second = await six_seats()
    nights = {"kills": {1: second}, "protects": {1: detective}, "shots": {2: doctor}}

    result = await play_game(config, puppets({2: everyone_votes_for(first)}, **nights))

    assert result.state.winner is Side.MURDERERS
    assert payloads(result.events, KillVoteCast, day=2) == []
    last = [type(e.payload).__name__ for e in result.events[-4:]]
    assert last == ["ResidentDied", "ResidentDied", "RolesRevealed", "GameEnded"]


# --- Who perceives the Night, and determinism ---------------------------------------------


async def test_night_events_are_perceived_only_by_the_residents_they_concern() -> None:
    result = await play_game(GameConfig(seed=7), scripted_bots(7))
    truth = GameState()
    seen: set[str] = set()

    for event in result.events:
        murderers_alive = set(truth.living_as(Role.MURDERER))
        truth.apply(event.payload)
        match event.payload:
            case DenMessagePosted() | KillVoteCast() | VictimChosen():
                assert set(event.visibility.residents) == murderers_alive
            case ResidentProtected(doctor=doctor):
                assert event.visibility.residents == (doctor,)
                assert truth.roles[doctor] is Role.DOCTOR
            case ResidentInvestigated(detective=detective):
                assert event.visibility.residents == (detective,)
                assert truth.roles[detective] is Role.DETECTIVE
            case AttackThwarted() | RecapNarrated() | ResidentDied():
                assert event.visibility.scope == "everyone"
            case _:
                continue
        seen.add(event.payload.type)
    assert seen >= {"den_message_posted", "kill_vote_cast", "victim_chosen", "resident_protected",
                    "resident_investigated", "recap_narrated"}  # fmt: skip


async def test_the_log_is_the_same_however_long_each_decision_takes() -> None:
    config = GameConfig(seed=7, max_days=3)
    bots = scripted_bots(config.seed)

    def jittery(resident: Resident) -> Brain:
        rng = Random(resident.name)
        return Delayed(bots(resident), lambda: rng.randrange(4))

    async def unhurried(event: Event) -> None:
        await asyncio.sleep(0)

    instant = await play_game(config, scripted_bots(config.seed))
    slow = await play_game(config, jittery, observers=[unhurried])

    assert [e.model_dump() for e in slow.events] == [e.model_dump() for e in instant.events]
