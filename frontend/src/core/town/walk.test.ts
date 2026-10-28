/** Seam 3 (unit): a Resident walking from one spot to another, on game time. */
import { describe, expect, it } from "vitest";

import { gridOf } from "../../../test/grid";
import { Walk } from "./walk";

const open = gridOf(".....", ".....", ".....");

describe("walking", () => {
  it("covers four tiles a second of game time", () => {
    const walk = new Walk({ x: 0.5, y: 0.5 }, { x: 4.5, y: 0.5 }, open);

    walk.advance(999);
    expect(walk.arrived).toBe(false);

    walk.advance(1);
    expect(walk.at).toEqual({ x: 4.5, y: 0.5 });
    expect(walk.arrived).toBe(true);
  });

  it("goes round what is in the way, through the middle of each tile, and ends exactly on the spot", () => {
    const walk = new Walk({ x: 0.5, y: 1.5 }, { x: 4.25, y: 1.75 }, gridOf(".....", ".###.", "....."));
    const passed: { x: number; y: number }[] = [];

    while (!walk.arrived) {
      walk.advance(50);
      passed.push(walk.at);
    }

    expect(passed.every(({ x, y }) => !(y > 1 && y < 2 && x > 1 && x < 4))).toBe(true);
    expect(walk.at).toEqual({ x: 4.25, y: 1.75 });
  });

  it("faces the way it is going", () => {
    const west = new Walk({ x: 4.5, y: 0.5 }, { x: 0.5, y: 0.5 }, open);
    const east = new Walk({ x: 0.5, y: 0.5 }, { x: 4.5, y: 0.5 }, open);

    west.advance(100);
    east.advance(100);

    expect(west.facing).toBe("left");
    expect(east.facing).toBe("right");
  });
});
