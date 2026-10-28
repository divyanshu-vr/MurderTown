/** Seam 3 (unit): how Residents find their way around town, one tile at a time. */
import { describe, expect, it } from "vitest";

import { gridOf as grid } from "../../../test/grid";
import { pathBetween, type Tile } from "./path";

function steps(way: readonly Tile[], from: Tile): number[] {
  let at = from;
  return way.map((tile) => {
    const size = Math.abs(tile.x - at.x) + Math.abs(tile.y - at.y);
    at = tile;
    return size;
  });
}

describe("finding a way", () => {
  it("takes the fewest steps, one tile up, down, left or right at a time", () => {
    const from = { x: 0, y: 0 };

    const way = pathBetween(grid(".....", ".....", "....."), from, { x: 4, y: 2 }) ?? [];

    expect(way).toHaveLength(6);
    expect(way.at(-1)).toEqual({ x: 4, y: 2 });
    expect(steps(way, from)).toEqual([1, 1, 1, 1, 1, 1]);
  });

  it("goes round what is in the way", () => {
    const from = { x: 0, y: 1 };

    const way = pathBetween(grid(".....", ".###.", "....."), from, { x: 4, y: 1 }) ?? [];

    expect(way).toHaveLength(6);
    expect(way.some(({ x, y }) => y === 1 && x > 0 && x < 4)).toBe(false);
  });

  it("finds no way to somewhere walled off, and stays put when already there", () => {
    const walled = grid("..#..", "..#..", "..#..");

    expect(pathBetween(walled, { x: 0, y: 0 }, { x: 4, y: 0 })).toBeNull();
    expect(pathBetween(walled, { x: 1, y: 1 }, { x: 1, y: 1 })).toEqual([]);
  });

  it("always finds the same way between the same tiles", () => {
    const open = grid("......", "......", "......", "......");
    const ways = Array.from({ length: 3 }, () => pathBetween(open, { x: 0, y: 3 }, { x: 5, y: 0 }));

    expect(ways[1]).toEqual(ways[0]);
    expect(ways[2]).toEqual(ways[0]);
  });
});
