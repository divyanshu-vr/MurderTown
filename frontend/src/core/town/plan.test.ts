/** Seam 3 (unit): the town as its map lays it out, read from the map the town is drawn from. */
import { describe, expect, it } from "vitest";

import town from "../../../assets/town/town.json";
import { present } from "../../../test/present";
import { pathBetween } from "./path";
import { inArea, planOf } from "./plan";

const plan = planOf(town);

describe("the town's plan", () => {
  it("has a door for each of fifteen seats, every one walkable and its own", () => {
    expect(plan.doors).toHaveLength(15);
    expect(new Set(plan.doors.map(({ x, y }) => `${x},${y}`)).size).toBe(15);
    expect(plan.doors.every(({ x, y }) => plan.grid.walkable(x, y))).toBe(true);
  });

  it("has a well in the middle of the square that nobody walks through", () => {
    expect(inArea(plan.square, plan.well)).toBe(true);
    expect(plan.grid.walkable(plan.well.x, plan.well.y)).toBe(false);
  });

  it("leads from every door, and from the town hall, to the square", () => {
    const corner = { x: plan.square.x, y: plan.square.y };

    for (const place of [...plan.doors, plan.hall]) {
      expect(pathBetween(plan.grid, place, corner)).not.toBeNull();
    }
  });

  it("has a den, lanterns, and spots for chores and wandering, every spot walkable, its own and reachable", () => {
    const spots = [plan.den, ...plan.chores, ...plan.wanders];

    expect(plan.lanterns.length).toBeGreaterThan(0);
    expect(plan.chores.length).toBeGreaterThan(0);
    expect(plan.wanders.length).toBeGreaterThanOrEqual(15);
    expect(new Set([...spots, ...plan.doors].map(({ x, y }) => `${x},${y}`)).size).toBe(spots.length + plan.doors.length);
    for (const spot of spots) {
      expect(plan.grid.walkable(spot.x, spot.y)).toBe(true);
      expect(pathBetween(plan.grid, spot, { x: plan.square.x, y: plan.square.y })).not.toBeNull();
    }
    expect(plan.grid.walkable(plan.denWindow.x, plan.denWindow.y)).toBe(false);
  });

  it("keeps everyone off houses and trees", () => {
    const door = present(plan.doors[0], "the first door");
    const roofOfTheFirstHouse = { x: door.x, y: door.y - 2 };

    expect(plan.grid.walkable(roofOfTheFirstHouse.x, roofOfTheFirstHouse.y)).toBe(false);
    expect(plan.grid.walkable(0, 0)).toBe(false);
  });
});
