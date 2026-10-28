"""The post-game review: turning points, lies and influence, read from a game's log.

Built on hand-made logs, so each rule is seen on its own; the recorded fixture's review is
checked in test_recorded_fixture.py.
"""

from mm.engine import Phase, Role
from mm.engine.decisions import Suspicion
from mm.engine.events import ResidentDied, SheriffFired
from mm.review import (
    KNOWS_GUILTY,
    KNOWS_INNOCENT,
    FalseClaim,
    Influence,
    LieAbout,
    Swing,
    TurningEvent,
    review_of,
)
from tests.hand_made import (
    C1,
    C2,
    C3,
    DET,
    DOC,
    M1,
    M2,
    SHERIFF,
    ballot,
    day,
    logged,
    says,
    suspects,
)


async def test_claiming_a_false_role_is_a_lie_told_beside_the_true_role_once_per_role() -> None:
    events = await logged(
        day(1),
        says(M1, claims=Role.CIVILIAN),
        says(M1, claims=Role.CIVILIAN),
        says(DOC, claims=Role.CIVILIAN),
        says(DET, claims=Role.DETECTIVE),
    )

    lies = review_of(events).lies

    assert lies == [
        FalseClaim(
            seq=lies[0].seq,
            speaker=M1,
            said=f"{M1} speaks.",
            claimed_role=Role.CIVILIAN,
            true_role=Role.MURDERER,
        ),
        FalseClaim(  # hiding a power is a false claim too
            seq=lies[1].seq,
            speaker=DOC,
            said=f"{DOC} speaks.",
            claimed_role=Role.CIVILIAN,
            true_role=Role.DOCTOR,
        ),
    ]


async def test_accusing_someone_privately_trusted_or_defending_someone_suspected_is_a_lie() -> None:
    events = await logged(
        day(1, Phase.DAWN),
        suspects(C1, c2=20, c3=80, doc=75),
        day(1),
        says(
            C1, accused=(C2, C3, SHERIFF)
        ),  # trusts C2; suspects C3; no suspicion of the Sheriff yet
        says(C1, defended=(DOC, C2)),  # suspects the Doctor; trusts C2
    )

    lies = review_of(events).lies

    assert [(lie.kind, lie.belief) for lie in lies if isinstance(lie, LieAbout)] == [
        ("accused_trusted", Suspicion(resident=C2, suspicion=20, note="c2 at 20")),
        ("defended_suspected", Suspicion(resident=DOC, suspicion=75, note="doc at 75")),
    ]
    assert [lie.said for lie in lies] == [f"{C1} speaks.", f"{C1} speaks."]


async def test_a_murderer_knows_who_is_innocent_and_who_is_a_fellow_murderer() -> None:
    events = await logged(
        day(1),
        says(M1, accused=(C1, M2), defended=(M2, C2)),
    )

    lies = review_of(events).lies

    assert [(lie.kind, lie.belief) for lie in lies if isinstance(lie, LieAbout)] == [
        ("accused_trusted", Suspicion(resident=C1, suspicion=0, note=KNOWS_INNOCENT)),
        ("defended_suspected", Suspicion(resident=M2, suspicion=100, note=KNOWS_GUILTY)),
    ]


async def test_nothing_said_about_the_dead_counts() -> None:
    events = await logged(
        ResidentDied(resident=C1, cause="murdered", role=Role.CIVILIAN),
        day(2),
        says(M1, accused=(C1,)),
    )

    review = review_of(events)

    assert review.lies == []
    assert review.influence == []


async def test_influence_is_how_often_others_voted_against_whom_a_resident_accused_that_day() -> (
    None
):
    events = await logged(
        day(1),
        says(C1, accused=(M1,)),
        says(C2, accused=(DOC,)),
        day(1, Phase.VOTE),
        ballot(C1, M1),  # their own ballot does not count
        ballot(C2, M1),
        ballot(DET, M1),
        ballot(SHERIFF, M1),
        ballot(M1, C1),
        ballot(DOC, None),  # a vote to skip follows nobody, but is still a ballot
        ballot(M2, C1),
        ballot(C3, C2),
        day(2),
        says(C3, accused=(M2,)),  # no Vote follows on Day 2: unranked
    )

    influence = review_of(events).influence

    assert influence == [
        Influence(resident=C1, followed=3, ballots=7),
        Influence(resident=C2, followed=0, ballots=7),
    ]


async def test_turning_points_are_deaths_the_sheriffs_shot_and_big_swings_in_suspicion() -> None:
    events = await logged(
        day(1, Phase.DAWN),
        suspects(C1, c2=20, sheriff=60),
        day(1, Phase.SHOWDOWN),
        SheriffFired(sheriff=SHERIFF, target=M1, hit_a_murderer=True),
        ResidentDied(resident=M1, cause="shot", role=Role.MURDERER),
        day(1, Phase.VOTE),
        suspects(C1, c2=70, sheriff=80),  # C2 swings by 50; the Sheriff only by 20
    )

    turning = review_of(events).turning_points

    shot = next(e.seq for e in events if isinstance(e.payload, SheriffFired))
    death = next(e.seq for e in events if isinstance(e.payload, ResidentDied))
    assert turning == [
        TurningEvent(seq=shot),
        TurningEvent(seq=death),
        Swing(seq=events[-1].seq, resident=C1, suspect=C2, before=20, after=70),
    ]
