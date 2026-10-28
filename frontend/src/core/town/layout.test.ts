/** Seam 3 (unit): where everyone stands in town for a view, from the recorded game and from towns of every size. */
import { describe, expect, it } from "vitest";

import town from "../../../assets/town/town.json";
import { present } from "../../../test/present";
import { countWhen, recordedGame } from "../../../test/recordedGame";
import { emptyView, foldEvents, type GameView, type ResidentView } from "../gameView";
import { layoutFor, type Placement } from "./layout";
import { pathBetween } from "./path";
import { type Area, planOf } from "./plan";

const plan = planOf(town);
const events = recordedGame();

/** The view once the `nth` Phase named `phase` has started. */
const viewWhen = (phase: GameView["phase"], nth = 1) => foldEvents(events.slice(0, countWhen(events, phase, nth)));

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

describe("where everyone stands", () => {
  it("by day, the living stand in a semicircle behind the well, each on a walkable spot of their own", () => {
    for (const phase of ["discussion", "showdown", "vote"] as const) {
      const placements = living(layoutFor(viewWhen(phase), plan));

      expect(placements).toHaveLength(12);
      expect(placements.every((placement) => within(plan.square, placement))).toBe(true);
      expect(placements.every((placement) => placement.at.y <= plan.well.y + 0.5)).toBe(true);
      expect(placements.every((placement) => plan.grid.walkable(tileOf(placement).x, tileOf(placement).y))).toBe(true);
    }
  });

  it("fits a town of any size into the semicircle, everyone at least a tile apart and able to walk there from home", () => {
    for (let size = 6; size <= 15; size += 1) {
      const placements = layoutFor(townOf(size, "discussion"), plan);

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
    const placements = layoutFor(townOf(15, "discussion"), plan);
    const middle = plan.well.x + 0.5;

    expect(placements.filter(({ at }) => at.x < middle - 0.5).every(({ facing }) => facing === "right")).toBe(true);
    expect(placements.filter(({ at }) => at.x > middle + 0.5).every(({ facing }) => facing === "left")).toBe(true);
  });

  it("keeps everyone at their own door before the game, at Dawn, at Dusk and at Night", () => {
    const views = [foldEvents(events.slice(0, 3)), viewWhen("dawn"), viewWhen("dusk"), viewWhen("night", 2)];

    for (const view of views) {
      const placements = living(layoutFor(view, plan));

      expect(placements.length).toBeGreaterThan(0);
      for (const placement of placements) {
        expect(tileOf(placement)).toEqual(doorOf(placement.seat));
      }
    }
  });

  it("leaves the dead where they died: in the square if banished or shot, at their door if murdered", () => {
    const daySpots = new Map(layoutFor(viewWhen("discussion"), plan).map((placement) => [placement.name, placement.at]));
    const end = layoutFor(foldEvents(events), plan);
    const placementOf = (name: string) => present(end.find((placement) => placement.name === name), name);

    for (const name of ["Ezra", "Bram", "Greta"]) {
      expect(placementOf(name)).toMatchObject({ dead: true, at: daySpots.get(name) });
    }
    const vera = placementOf("Vera");
    expect(vera.dead).toBe(true);
    expect(tileOf(vera)).toEqual(doorOf(vera.seat));
  });

  it("gathers the living in the square once the game has ended", () => {
    const placements = living(layoutFor(foldEvents(events), plan));

    expect(placements.length).toBeGreaterThan(0);
    expect(placements.every((placement) => within(plan.square, placement))).toBe(true);
  });
});
