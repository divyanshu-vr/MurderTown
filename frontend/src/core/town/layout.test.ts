/** Seam 3 (unit): where everyone stands in town for a view, from the recorded game and from towns of every size. */
import { describe, expect, it } from "vitest";

import town from "../../../assets/town/town.json";
import { present } from "../../../test/present";
import { countOf as countAt, countWhen, eventsOf, recordedGame } from "../../../test/recordedGame";
import type { Event } from "../../protocol";
import { emptyView, foldEvents, type GameView, isPublic, type ResidentView } from "../gameView";
import { layoutFor, middleOf, type Placement, type Point } from "./layout";
import { pathBetween, type Tile } from "./path";
import { type Area, CHORE_KINDS, planOf } from "./plan";
import { stageOf } from "./stage";

const plan = planOf(town);
const events = recordedGame();

/** Where everyone stands once the first `count` events of what is `shown` have happened. */
function layoutAt(count: number, shown: readonly Event[] = events): Placement[] {
  const happened = shown.filter((event) => event.seq <= (events[count - 1]?.seq ?? 0));
  return layoutFor(foldEvents(happened), stageOf(happened), plan);
}
const layoutWhen = (phase: GameView["phase"], nth = 1) => layoutAt(countWhen(events, phase, nth));
const countOf = (event: Event) => countAt(events, event);

function townOf(size: number, phase: GameView["phase"]): GameView {
  const residents: ResidentView[] = Array.from({ length: size }, (_, seat) => ({
    name: `Resident ${seat}`,
    seat,
    occupation: "baker",
    role: null,
    revealed: false,
    fate: null,
  }));
  return { ...emptyView, residents, phase };
}

const within = (area: Area, { at }: Placement) =>
  at.x > area.x && at.y > area.y && at.x < area.x + area.width && at.y < area.y + area.height;
const tileOf = ({ at }: Placement) => ({ x: Math.floor(at.x), y: Math.floor(at.y) });
const living = (placements: readonly Placement[]) => placements.filter((placement) => !placement.dead);
const doorOf = (seat: number) => present(plan.doors[seat], `a door for seat ${seat}`);
const named = (placements: readonly Placement[], name: string) =>
  present(placements.find((placement) => placement.name === name), name);
const near = (at: Point, tile: Tile, tiles: number) => Math.hypot(at.x - middleOf(tile).x, at.y - middleOf(tile).y) <= tiles;
const onSpot = (placement: Placement, spots: readonly Tile[]) =>
  spots.some((spot) => spot.x === tileOf(placement).x && spot.y === tileOf(placement).y);

function expectATileEach(placements: readonly Placement[]) {
  const tiles = living(placements).map((placement) => `${tileOf(placement).x},${tileOf(placement).y}`);
  expect(new Set(tiles).size).toBe(tiles.length);
  for (const placement of living(placements)) expect(plan.grid.walkable(tileOf(placement).x, tileOf(placement).y)).toBe(true);
}

describe("where everyone stands by day", () => {
  it("has the living in a semicircle behind the well, each on a walkable spot of their own", () => {
    for (const phase of ["discussion", "showdown", "vote"] as const) {
      const placements = living(layoutWhen(phase));

      expect(placements).toHaveLength(12);
      expect(placements.every((placement) => within(plan.square, placement))).toBe(true);
      expect(placements.every((placement) => placement.at.y <= plan.well.y + 0.5)).toBe(true);
      expect(placements.every((placement) => plan.grid.walkable(tileOf(placement).x, tileOf(placement).y))).toBe(true);
    }
  });

  it("fits a town of any size into the semicircle, everyone at least a tile apart and able to walk there from home", () => {
    for (let size = 6; size <= 15; size += 1) {
      const placements = layoutFor(townOf(size, "discussion"), stageOf([]), plan);

      for (const [index, placement] of placements.entries()) {
        expect(within(plan.square, placement)).toBe(true);
        expect(pathBetween(plan.grid, doorOf(placement.seat), tileOf(placement))).not.toBeNull();
        for (const other of placements.slice(index + 1)) {
          expect(Math.hypot(placement.at.x - other.at.x, placement.at.y - other.at.y)).toBeGreaterThanOrEqual(1);
        }
      }
    }
  });

  it("turns everyone in the square towards the well", () => {
    const placements = layoutFor(townOf(15, "discussion"), stageOf([]), plan);
    const middle = plan.well.x + 0.5;

    expect(placements.filter(({ at }) => at.x < middle - 0.5).every(({ facing }) => facing === "right")).toBe(true);
    expect(placements.filter(({ at }) => at.x > middle + 0.5).every(({ facing }) => facing === "left")).toBe(true);
  });

  it("keeps everyone at their own door before the game and at Dawn", () => {
    for (const placements of [layoutAt(3), layoutWhen("dawn"), layoutWhen("dawn", 3)]) {
      expect(living(placements).length).toBeGreaterThan(0);
      for (const placement of living(placements)) expect(tileOf(placement)).toEqual(doorOf(placement.seat));
    }
  });

  it("leaves the dead where they died: in the square if banished or shot, at their door if murdered", () => {
    const daySpots = new Map(layoutWhen("discussion").map((placement) => [placement.name, placement.at]));
    const end = layoutAt(events.length);

    for (const name of ["Ezra", "Bram", "Greta"]) {
      expect(named(end, name)).toMatchObject({ dead: true, at: daySpots.get(name) });
    }
    const vera = named(end, "Vera");
    expect(vera.dead).toBe(true);
    expect(tileOf(vera)).toEqual(doorOf(vera.seat));
  });

  it("gathers the living in the square once the game has ended", () => {
    const placements = living(layoutAt(events.length));

    expect(placements.length).toBeGreaterThan(0);
    expect(placements.every((placement) => within(plan.square, placement))).toBe(true);
  });
});

describe("where everyone stands at Dusk", () => {
  const [, , , secondWave] = eventsOf(events, "conversation_started");
  const endOfTheFirstWave = countOf(present(secondWave, "a second wave")) - 1;
  const stage = stageOf(events.slice(0, endOfTheFirstWave));

  it("puts each pair side by side about halfway between their homes, facing each other", () => {
    const placements = layoutAt(endOfTheFirstWave);

    expect(stage.pairs.length).toBeGreaterThan(1);
    for (const [one, other] of stage.pairs) {
      const [a, b] = [named(placements, one), named(placements, other)];
      const [left, right] = a.at.x < b.at.x ? [a, b] : [b, a];
      const [homeA, homeB] = [middleOf(doorOf(a.seat)), middleOf(doorOf(b.seat))];

      expect([right.at.x - left.at.x, right.at.y - left.at.y]).toEqual([1, 0]);
      expect([left.facing, right.facing]).toEqual(["right", "left"]);
      expect(Math.hypot((a.at.x + b.at.x - homeA.x - homeB.x) / 2, (a.at.y + b.at.y - homeA.y - homeB.y) / 2)).toBeLessThanOrEqual(4);
    }
  });

  it("sends those doing a Chore to a chore spot, to do the Chore it is for, and the rest wandering", () => {
    const placements = living(layoutAt(endOfTheFirstWave));
    const talking = new Set(stage.pairs.flat());

    for (const placement of placements.filter(({ name }) => !talking.has(name))) {
      if (stage.activities.get(placement.name) === "chore") {
        const at = tileOf(placement);
        const spot = plan.chores.find(({ x, y }) => x === at.x && y === at.y);
        expect(spot).toBeDefined();
        expect(placement.chore).toBe(spot?.kind);
      } else {
        expect(onSpot(placement, plan.wanders)).toBe(true);
        expect(placement.chore).toBeNull();
      }
    }
    expectATileEach(placements);
  });

  it("keeps pairs off the chore and wander spots, and everyone off the lanterns", () => {
    const placements = living(layoutAt(endOfTheFirstWave));
    const talking = new Set(stage.pairs.flat());

    for (const placement of placements) {
      if (talking.has(placement.name)) expect(onSpot(placement, [...plan.chores, ...plan.wanders])).toBe(false);
      expect(onSpot(placement, plan.lanterns)).toBe(false);
    }
  });

  it("has every kind of Chore done at some Dusk of the recorded game", () => {
    const endsOfDusk = eventsOf(events, "phase_started")
      .filter(({ payload }) => payload.phase === "night")
      .map((night) => countOf(night) - 1);
    const done = new Set(endsOfDusk.flatMap((count) => layoutAt(count).map(({ chore }) => chore)));

    expect(done).toEqual(new Set([...CHORE_KINDS, null]));
  });

  it("turns those at a Chore towards what they work at", () => {
    const atChores = living(layoutAt(endOfTheFirstWave)).filter((placement) => placement.chore !== null);

    expect(atChores.length).toBeGreaterThan(0);
    for (const placement of atChores) {
      const { x, y } = tileOf(placement);
      expect(plan.grid.walkable(placement.facing === "left" ? x - 1 : x + 1, y)).toBe(false);
    }
  });

  it("moves the wanderers on as Dusk goes by", () => {
    const early = layoutAt(countWhen(events, "dusk", 1) + 1);
    const later = layoutAt(endOfTheFirstWave);
    const wanderers = [...stage.activities].filter(([, activity]) => activity === "wander").map(([name]) => name);
    const moved = (name: string) => named(early, name).at.x !== named(later, name).at.x || named(early, name).at.y !== named(later, name).at.y;

    expect(wanderers.some(moved)).toBe(true);
  });
});

describe("where everyone stands at Night", () => {
  const denMessage = present(eventsOf(events, "den_message_posted")[0], "a Den message");
  const investigated = present(eventsOf(events, "resident_investigated")[0], "an investigation");
  const victim = present(eventsOf(events, "victim_chosen")[0], "a Victim").payload;
  const protectedOne = present(eventsOf(events, "resident_protected")[0], "a protection").payload;

  it("has the Murderers meet at the Den while everyone else is at home", () => {
    const placements = layoutAt(countOf(denMessage));

    for (const placement of living(placements)) {
      if (denMessage.payload.den.includes(placement.name)) expect(near(placement.at, plan.den, 1.5)).toBe(true);
      else expect(tileOf(placement)).toEqual(doorOf(placement.seat));
    }
    expectATileEach(placements);
  });

  it("sends the Murderers, the Doctor and the Detective each to the house of whom they chose", () => {
    const placements = layoutAt(countOf(investigated));
    const visiting = new Map([
      ...victim.den.map((murderer) => [murderer, victim.victim] as const),
      [protectedOne.doctor, protectedOne.target],
      [investigated.payload.detective, investigated.payload.target],
    ]);

    for (const placement of living(placements)) {
      const target = visiting.get(placement.name);
      if (target) expect(near(placement.at, doorOf(named(placements, target).seat), 1.5)).toBe(true);
      else expect(tileOf(placement)).toEqual(doorOf(placement.seat));
    }
    expectATileEach(placements);
  });

  it("keeps a Doctor who protects themselves at home", () => {
    const own = present(
      eventsOf(events, "resident_protected").find(({ payload }) => payload.doctor === payload.target),
      "a Doctor protecting themselves",
    );
    const doctor = named(layoutAt(countOf(own)), own.payload.doctor);

    expect(tileOf(doctor)).toEqual(doorOf(doctor.seat));
  });

  it("in mystery mode keeps everyone at home all Night", () => {
    const placements = layoutAt(countOf(investigated), events.filter(isPublic));

    for (const placement of living(placements)) expect(tileOf(placement)).toEqual(doorOf(placement.seat));
  });
});
