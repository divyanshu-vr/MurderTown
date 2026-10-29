/** Seam 3 (unit): every Night Visit the map allows plays well within the time playback waits for it. */
import { describe, expect, it } from "vitest";

import town from "../../../assets/town/town.json";
import { ANIMATION_TIMEOUT_MS } from "../playback";
import { pathBetween, type Tile } from "./path";
import { planOf } from "./plan";
import { visitMs } from "./visit";

const plan = planOf(town);

/** How many tiles a walk from one tile to another takes on the map. */
function tilesBetween(from: Tile, to: Tile): number {
  const path = pathBetween(plan.grid, from, to);
  if (!path) throw new Error(`no way from ${JSON.stringify(from)} to ${JSON.stringify(to)}`);
  return path.length - 1;
}

describe("a Night Visit", () => {
  it("takes at most three quarters of the time playback waits, from the Den or any door to any other", () => {
    const visits = plan.doors.flatMap((home) =>
      plan.doors.flatMap((door) => [
        visitMs(tilesBetween(plan.den, door), tilesBetween(door, home)), // a Murderer, from the Den
        visitMs(tilesBetween(home, door), tilesBetween(door, home)), // the Doctor or the Detective
      ]),
    );

    expect(Math.max(...visits)).toBeLessThan(ANIMATION_TIMEOUT_MS * 0.75);
  });
});
